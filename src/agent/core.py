from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_openai import ChatOpenAI

from src.agent.prompts import REACT_SYSTEM, format_tool_descriptions
from src.agent.tools.write_file import make_write_file_tool
from src.agent.tools.read_file import make_read_file_tool
from src.agent.tools.execute_code import make_execute_code_tool
from src.agent.tools.save_skill import make_save_skill_tool
from src.agent.tools.list_skills import make_list_skills_tool
from src.agent.tools.run_skill import make_run_skill_tool
from src.config import Settings
from src.db.repositories.skills import SkillsRepository
from src.sandbox.manager import SandboxManager

logger = logging.getLogger(__name__)

# Regex to parse Action/Action Input from model output
_ACTION_RE = re.compile(
    r"Action\s*:\s*(.+?)\s*\n\s*Action\s+Input\s*:\s*(.+)",
    re.DOTALL,
)
_FINAL_RE = re.compile(r"Final\s+Answer\s*:\s*(.+)", re.DOTALL)


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


def build_llm(settings: Settings) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key.get_secret_value(),
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        stop=["\nObservation:", "\nObservation "],
    )


class ReactAgent:
    """Simple text-based ReAct agent that doesn't require native tool calling."""

    def __init__(
        self,
        llm: ChatOpenAI,
        tools: list,
        max_iterations: int = 10,
    ) -> None:
        self.llm = llm
        self.tools = {t.name: t for t in tools}
        self.tool_list = tools
        self.max_iterations = max_iterations

    async def ainvoke(
        self,
        input_data: dict[str, str],
        config: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        task = input_data["input"]
        callbacks: list[AsyncCallbackHandler] = []
        if config and "callbacks" in config:
            callbacks = config["callbacks"]

        tool_desc = format_tool_descriptions(self.tool_list)
        system = REACT_SYSTEM.format(tool_descriptions=tool_desc)

        conversation = f"{system}\n\nTask: {task}\nThought:"
        final_answer = ""

        for i in range(self.max_iterations):
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

            # Check for Final Answer
            final_match = _FINAL_RE.search(text)
            if final_match:
                final_answer = final_match.group(1).strip()
                logger.info("[iter %d] Final answer: %.200s", i, final_answer)
                break

            # Parse Action
            action_match = _ACTION_RE.search(text)
            if not action_match:
                logger.warning("[iter %d] No Action found, retrying", i)
                conversation += f" {text}\nObservation: Please use the exact format: Action: <tool_name>\\nAction Input: <json>\\nThought:"
                continue

            tool_name = action_match.group(1).strip()
            raw_input = action_match.group(2).strip()
            # Clean raw_input: take only the first JSON object or first line
            raw_input = _extract_json(raw_input)
            logger.info("[iter %d] Action: %s | Input: %.300s", i, tool_name, raw_input)

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
            else:
                tool = self.tools[tool_name]
                try:
                    args = json.loads(raw_input)
                    if isinstance(args, dict):
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
            logger.info("[iter %d] Observation (%d chars): %.200s", i, len(obs_str), obs_str)

            # Truncate long observations
            if len(obs_str) > 5000:
                obs_str = obs_str[:5000] + "\n... (truncated)"

            # Build next prompt turn
            conversation += f" {text}\nObservation: {obs_str}\nThought:"

        if not final_answer:
            final_answer = "Max iterations reached. Last observation may contain partial results."

        return {"output": final_answer}


def build_agent(
    settings: Settings,
    sandbox: SandboxManager,
    skill_repo: SkillsRepository,
    workspace_path: str,
    user_id: int,
) -> ReactAgent:
    llm = build_llm(settings)

    tools = [
        make_write_file_tool(workspace_path),
        make_read_file_tool(workspace_path),
        make_execute_code_tool(sandbox, workspace_path),
        make_save_skill_tool(skill_repo, workspace_path, user_id),
        make_list_skills_tool(skill_repo),
        make_run_skill_tool(skill_repo, sandbox),
    ]

    return ReactAgent(
        llm=llm,
        tools=tools,
        max_iterations=settings.agent_max_iterations,
    )
