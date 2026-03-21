from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_openai import ChatOpenAI

from src.agent.prompts import get_prompts, format_tool_descriptions
from src.agent.summarizer import OBSERVATION_SUMMARIZE_THRESHOLD, summarize_observation
from src.agent.tools.write_file import make_write_file_tool
from src.agent.tools.read_file import make_read_file_tool
from src.agent.tools.execute_code import make_execute_code_tool
from src.agent.tools.save_skill import make_save_skill_tool
from src.agent.tools.list_skills import make_list_skills_tool
from src.agent.tools.run_skill import make_run_skill_tool
from src.config import Settings
from src.db.models import ConversationMessage
from src.db.repositories.skills import SkillsRepository
from src.sandbox.manager import SandboxManager

logger = logging.getLogger(__name__)

# Regex to parse Action/Action Input from model output
_ACTION_RE = re.compile(
    r"Action\s*:\s*(.+?)\s*\n\s*Action\s+Input\s*:\s*(.+)",
    re.DOTALL,
)
_FINAL_RE = re.compile(r"Final\s+Answer\s*:\s*(.+)", re.DOTALL)

# Conservative estimate: 1 token ≈ 3 chars (safe for mixed Cyrillic/Latin)
_CHARS_PER_TOKEN = 3


def _normalize_tool_args(tool, args: dict) -> dict:
    """Fix common small-LLM mistakes: wrong field names, double-serialised JSON."""
    schema_cls = getattr(tool, "args_schema", None)
    if schema_cls is None:
        return args

    schema = schema_cls.model_json_schema()
    required = set(schema.get("required", []))
    props = set(schema.get("properties", {}).keys())

    # Already valid — fast path
    if required.issubset(args.keys()):
        return args

    # Pattern 1: a value is a JSON string containing the correct fields
    # e.g. {"filename": '{"filename":"main.py","content":"..."}'}
    for val in args.values():
        if isinstance(val, str) and val.strip().startswith("{"):
            try:
                parsed = json.loads(val)
                if isinstance(parsed, dict) and required.issubset(parsed.keys()):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass

    # Pattern 2: wrong field names — map extra keys to missing required fields
    missing = list(required - set(args.keys()))
    extra = [k for k in args if k not in props]
    if missing and extra:
        remapped = dict(args)
        for m, e in zip(missing, extra):
            remapped[m] = remapped.pop(e)
        if required.issubset(remapped.keys()):
            return remapped

    # Pattern 3: single required field missing — take first string value
    if len(missing) == 1:
        for v in args.values():
            if isinstance(v, str):
                fixed = dict(args)
                fixed[missing[0]] = v
                return fixed

    return args


def _extract_json(raw: str) -> str:
    """Extract the first JSON object from raw string.
    Models often continue writing after the JSON — this trims the excess."""
    raw = raw.strip()
    if not raw.startswith("{"):
        # Not JSON — return first line
        return raw.split("\n")[0].strip()
    depth = 0
    in_str = False
    escape = False
    for i, ch in enumerate(raw):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"' and not escape:
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return raw[: i + 1]
    return raw  # fallback: return as-is


def build_llm(settings: Settings, react_mode: bool = True) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key.get_secret_value(),
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        stop=["\nObservation:", "\nObservation "] if react_mode else None,
    )


class ReactAgent:
    """Simple text-based ReAct agent that doesn't require native tool calling."""

    LOOP_WINDOW = 6  # how many recent actions to track
    LOOP_THRESHOLD = 3  # same action repeated this many times = loop

    _FAILURE_PHRASES = [
        "unable to", "i failed", "i could not", "i cannot",
        "failed to retrieve", "failed to complete", "repeated failures",
        "unable to retrieve", "unable to complete",
    ]

    def __init__(
        self,
        llm: ChatOpenAI,
        tools: list,
        max_iterations: int = 200,
        system_prompt: str | None = None,
        required_tool: str | None = None,
        required_tools_any: set[str] | None = None,
        required_tools_any_min_length: int = 80,
        settings: Settings | None = None,
        required_plan_tool: str | None = None,
        action_tool_names: set[str] | None = None,
        min_plans_before_failure: int = 2,
    ) -> None:
        self.llm = llm
        self.tools = {t.name: t for t in tools}
        self.tool_list = tools
        self.max_iterations = max_iterations
        self.system_prompt = system_prompt
        self.required_tool = required_tool
        self.required_tools_any = required_tools_any
        self.required_tools_any_min_length = required_tools_any_min_length
        self.settings = settings
        self.required_plan_tool = required_plan_tool
        self.action_tool_names = action_tool_names or set()
        self.min_plans_before_failure = min_plans_before_failure

    def _is_failure_answer(self, text: str) -> bool:
        lower = text.lower()[:500]
        return any(p in lower for p in self._FAILURE_PHRASES)

    def _detect_loop(self, history: list[tuple[str, str]]) -> bool:
        """Check if the agent is stuck in a loop.
        Returns True if the same (tool, input) pair appears >= LOOP_THRESHOLD
        times in the last LOOP_WINDOW actions."""
        window = history[-self.LOOP_WINDOW :]
        if len(window) < self.LOOP_THRESHOLD:
            return False
        from collections import Counter
        counts = Counter(window)
        return any(c >= self.LOOP_THRESHOLD for c in counts.values())

    def _trim_to_fit(self, conversation: str) -> str:
        """Drop oldest turns when conversation approaches context window limit."""
        if not self.settings:
            return conversation
        max_input_tokens = self.settings.llm_context_size - self.settings.llm_max_tokens
        max_chars = max_input_tokens * _CHARS_PER_TOKEN
        if len(conversation) <= max_chars:
            return conversation

        sep = "\nObservation:"
        parts = conversation.split(sep)
        if len(parts) <= 2:
            return conversation

        header = parts[0]  # system prompt + task + first Thought
        note = " [... earlier turns trimmed to fit context window ...]\nThought: Continuing."

        for keep_last in range(len(parts) - 1, 0, -1):
            tail = sep.join(parts[-keep_last:])
            candidate = header + sep + note + sep + tail
            if len(candidate) <= max_chars:
                dropped = len(parts) - 1 - keep_last
                logger.info(
                    "Context trimmed: dropped %d turns, keeping %d",
                    dropped, keep_last,
                )
                return candidate

        return header + sep + note + sep + parts[-1]

    async def ainvoke(
        self,
        input_data: dict[str, str],
        config: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        task = input_data["input"]
        callbacks: list[AsyncCallbackHandler] = []
        if config and "callbacks" in config:
            callbacks = config["callbacks"]

        conv_repo = config.get("conversation_repo") if config else None
        task_id = config.get("task_id") if config else None
        prompt_logger = config.get("prompt_logger") if config else None

        async def _save(role: str, content: str, tool_name: str | None = None) -> None:
            if conv_repo and task_id:
                await conv_repo.add(ConversationMessage(
                    task_id=task_id, role=role, content=content[:10000],
                    tool_name=tool_name,
                ))

        tool_desc = format_tool_descriptions(self.tool_list)
        if prompt_logger:
            prompt_logger.log("tool_descriptions", tool_desc)
        prompts = get_prompts(self.settings.prompt_language) if self.settings else get_prompts()
        prompt_template = self.system_prompt or prompts.REACT_SYSTEM
        system = prompt_template.format(tool_descriptions=tool_desc)
        if prompt_logger:
            prompt_logger.log("system", system)

        conversation = f"{system}\n\nTask: {task}\nThought:"
        if prompt_logger:
            prompt_logger.log("full_prompt", conversation)
        final_answer = ""
        action_history: list[tuple[str, str]] = []
        tools_called: set[str] = set()
        required_tool_nags = 0
        required_tools_any_nags = 0
        delegation_fail_count = 0
        plan_count = 0
        plan_nags = 0
        failure_plan_nags = 0

        await _save("system", system)
        await _save("user", task)

        for i in range(self.max_iterations):
            conversation = self._trim_to_fit(conversation)
            logger.info("[iter %d] Calling LLM (prompt len=%d)", i, len(conversation))

            # Call LLM
            try:
                response = await self.llm.ainvoke(conversation)
            except Exception as e:
                logger.exception("[iter %d] LLM call failed", i)
                final_answer = f"LLM error: {e}"
                break

            text = response.content if isinstance(response.content, str) else str(response.content)
            logger.info("[iter %d] LLM response (%d chars): %.300s", i, len(text), text)
            if prompt_logger:
                prompt_logger.log_response(i, text)
            await _save("assistant", text)

            # Parse both Action and Final Answer
            action_match = _ACTION_RE.search(text)
            final_match = _FINAL_RE.search(text)

            # If both found, whichever comes first wins
            if action_match and final_match:
                if final_match.start() < action_match.start():
                    action_match = None  # Final Answer comes first
                else:
                    final_match = None  # Action comes first, process it

            if final_match and not action_match:
                # Guard: if required_tool not yet called, reject Final Answer
                if (
                    self.required_tool
                    and self.required_tool not in tools_called
                    and required_tool_nags < 3
                ):
                    required_tool_nags += 1
                    logger.warning(
                        "[iter %d] Premature Final Answer — %s not called yet (nag %d/3)",
                        i, self.required_tool, required_tool_nags,
                    )
                    conversation += (
                        f" {text}\nObservation: STOP. You have NOT called "
                        f"{self.required_tool} yet. The skill is NOT saved. "
                        f"You MUST call {self.required_tool} before Final Answer.\nThought:"
                    )
                    continue
                candidate_answer = final_match.group(1).strip()
                if (
                    self.required_tools_any
                    and not tools_called.intersection(self.required_tools_any)
                    and len(candidate_answer) >= self.required_tools_any_min_length
                    and required_tools_any_nags < 3
                ):
                    required_tools_any_nags += 1
                    tool_names = ", ".join(sorted(self.required_tools_any))
                    logger.warning(
                        "[iter %d] No research tool called, nag %d/3",
                        i, required_tools_any_nags,
                    )
                    conversation += (
                        f" {text}\nObservation: STOP. You have not used any research tool. "
                        f"Your answer may contain fabricated information. "
                        f"You MUST call at least one of: {tool_names} before Final Answer. "
                        f"Use web_search to verify your claims.\nThought:"
                    )
                    continue
                # Plan enforcement: reject failure answers until enough replanning
                if (
                    self.required_plan_tool
                    and self._is_failure_answer(candidate_answer)
                    and plan_count < self.min_plans_before_failure
                    and failure_plan_nags < 3
                ):
                    failure_plan_nags += 1
                    logger.warning(
                        "[iter %d] Failure answer rejected — only %d plan(s), need %d (nag %d/3)",
                        i, plan_count, self.min_plans_before_failure, failure_plan_nags,
                    )
                    conversation += (
                        f" {text}\nObservation: STOP. Your answer says you failed, but you have "
                        f"only tried {plan_count} approach(es). You MUST try at least "
                        f"{self.min_plans_before_failure} different approaches before giving up. "
                        f"Analyze WHY the previous approach failed, think of a COMPLETELY "
                        f"different method (different website, different API, different tool), "
                        f"call {self.required_plan_tool} with a NEW plan, then execute it.\nThought:"
                    )
                    continue
                final_answer = candidate_answer
                logger.info("[iter %d] Final answer: %.200s", i, final_answer)
                break
            if not action_match:
                logger.warning("[iter %d] No Action found, retrying", i)
                conversation += f" {text}\nObservation: Please use the exact format: Action: <tool_name>\\nAction Input: <json>\\nThought:"
                continue

            tool_name = action_match.group(1).strip()
            raw_input = action_match.group(2).strip()
            # Clean raw_input: take only the first JSON object or first line
            raw_input = _extract_json(raw_input)
            logger.info("[iter %d] Action: %s | Input: %.300s", i, tool_name, raw_input)

            # Loop detection
            action_history.append((tool_name, raw_input))
            if self._detect_loop(action_history):
                logger.warning("[iter %d] Loop detected! Same action repeated %d times. Stopping.", i, self.LOOP_THRESHOLD)
                conversation += f" {text}\nObservation: LOOP DETECTED — you have repeated the same action {self.LOOP_THRESHOLD} times. Stop and provide a Final Answer with what you have so far.\nThought:"
                continue

            # Notify callbacks
            for cb in callbacks:
                try:
                    await cb.on_tool_start({"name": tool_name}, raw_input)
                except Exception:
                    pass

            # Execute tool
            if tool_name not in self.tools:
                observation = f"Error: unknown tool '{tool_name}'. Available: {', '.join(self.tools.keys())}"
                logger.warning("[iter %d] Unknown tool: %s", i, tool_name)
            elif (
                self.required_plan_tool
                and tool_name in self.action_tool_names
                and self.required_plan_tool not in tools_called
                and plan_nags < 3
            ):
                plan_nags += 1
                observation = (
                    f"BLOCKED: You must call {self.required_plan_tool} with your "
                    f"step-by-step plan BEFORE using {tool_name}. "
                    f"Think about what steps are needed, build a numbered plan "
                    f"(2-5 steps), and show it to the user first."
                )
                logger.warning(
                    "[iter %d] Action %s blocked — plan not shown yet (nag %d/3)",
                    i, tool_name, plan_nags,
                )
            else:
                tool = self.tools[tool_name]
                try:
                    args = json.loads(raw_input)
                    if isinstance(args, dict):
                        args = _normalize_tool_args(tool, args)
                        observation = await tool.ainvoke(args)
                    else:
                        observation = await tool.ainvoke(str(args))
                except json.JSONDecodeError:
                    observation = await tool.ainvoke(raw_input)
                except Exception as e:
                    logger.exception("[iter %d] Tool %s error", i, tool_name)
                    observation = f"Tool error: {e}"
                    for cb in callbacks:
                        try:
                            await cb.on_tool_error(e)
                        except Exception:
                            pass

            obs_str = str(observation)
            tools_called.add(tool_name)
            if tool_name == self.required_plan_tool:
                plan_count += 1
            logger.info("[iter %d] Observation (%d chars): %.200s", i, len(obs_str), obs_str)
            await _save("tool", obs_str, tool_name=tool_name)

            # Track delegate_to_coder failures
            if tool_name == "delegate_to_coder" and "WARNING: No skill was saved" in obs_str:
                delegation_fail_count += 1
                if delegation_fail_count >= 2:
                    obs_str += (
                        "\n\n>>> SYSTEM: delegate_to_coder has failed "
                        f"{delegation_fail_count} times. STOP delegating. "
                        "Use web_search to answer the user directly with whatever data you can find."
                    )

            # Auto-summarize or truncate long observations
            if len(obs_str) > OBSERVATION_SUMMARIZE_THRESHOLD and self.settings:
                summary_llm = build_llm(self.settings, react_mode=False)
                try:
                    obs_str = await summarize_observation(summary_llm, obs_str)
                except Exception:
                    obs_str = obs_str[:5000] + "\n... (truncated)"
            elif len(obs_str) > 5000:
                obs_str = obs_str[:5000] + "\n... (truncated)"

            # Build next prompt turn
            conversation += f" {text}\nObservation: {obs_str}\nThought:"

        if not final_answer:
            final_answer = "Max iterations reached. Last observation may contain partial results."

        return {"output": final_answer}


def build_coder_agent(
    settings: Settings,
    sandbox: SandboxManager,
    skill_repo: SkillsRepository,
    workspace_path: str,
    user_id: int,
    system_prompt_override: str | None = None,
) -> ReactAgent:
    llm = build_llm(settings)

    tools = [
        make_write_file_tool(workspace_path),
        make_read_file_tool(workspace_path),
        make_execute_code_tool(sandbox, workspace_path),
        make_save_skill_tool(skill_repo, workspace_path, user_id, settings.skills_dir),
        make_list_skills_tool(skill_repo),
        make_run_skill_tool(skill_repo, sandbox),
    ]

    prompts = get_prompts(settings.prompt_language)
    return ReactAgent(
        llm=llm,
        tools=tools,
        max_iterations=settings.agent_max_iterations,
        system_prompt=system_prompt_override or prompts.CODER_SYSTEM,
        required_tool="save_skill",
        settings=settings,
    )


def build_code_reviewer_agent(
    settings: Settings,
    sandbox: SandboxManager,
    workspace_path: str,
    system_prompt_override: str | None = None,
) -> ReactAgent:
    llm = build_llm(settings)
    tools = [
        make_read_file_tool(workspace_path),
        make_write_file_tool(workspace_path),
        make_execute_code_tool(sandbox, workspace_path),
    ]
    prompts = get_prompts(settings.prompt_language)
    return ReactAgent(
        llm=llm,
        tools=tools,
        max_iterations=15,
        system_prompt=system_prompt_override or prompts.CODE_REVIEWER_SYSTEM,
        settings=settings,
    )


def build_file_analyzer_agent(
    settings: Settings,
    sandbox: SandboxManager,
    workspace_path: str,
    system_prompt_override: str | None = None,
) -> ReactAgent:
    llm = build_llm(settings)
    tools = [
        make_read_file_tool(workspace_path),
        make_write_file_tool(workspace_path),
        make_execute_code_tool(sandbox, workspace_path),
    ]
    prompts = get_prompts(settings.prompt_language)
    return ReactAgent(
        llm=llm,
        tools=tools,
        max_iterations=20,
        system_prompt=system_prompt_override or prompts.FILE_ANALYZER_SYSTEM,
        settings=settings,
    )
