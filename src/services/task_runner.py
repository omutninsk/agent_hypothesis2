from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING
from uuid import UUID

from src.agent.callbacks import TransportProgressCallback
from src.agent.planner import PlanState
from src.agent.prompt_logger import PromptBlockLogger
from src.agent.prompts import get_prompts
from src.agent.supervisor import build_supervisor_agent
from src.agent.tools.show_plan import make_show_plan_tool
from src.config import Settings
from src.db.models import MemoryEntry, Task, TaskStatus
from src.db.repositories.knowledge import KnowledgeRepository
from src.db.repositories.memory import MemoryRepository
from src.db.repositories.skills import SkillsRepository
from src.db.repositories.conversations import ConversationsRepository
from src.db.repositories.tasks import TasksRepository
from src.sandbox.manager import SandboxManager
from src.services.reflection import reflect_and_save
from src.services.validation import validate_response

if TYPE_CHECKING:
    from src.db.repositories.scheduled_tasks import ScheduledTasksRepository
    from src.transport.protocol import ChatTransport

logger = logging.getLogger(__name__)

_FAILURE_PHRASES = [
    "unable to",
    "i failed",
    "i could not",
    "max iterations reached",
    "i cannot",
    "failed to retrieve",
    "failed to complete",
    "repeated failures",
    "unable to retrieve",
    "unable to complete",
]


def _is_failure_answer(answer: str) -> bool:
    """Detect if the agent's answer is essentially a failure explanation."""
    lower = answer.lower()[:500]
    return any(phrase in lower for phrase in _FAILURE_PHRASES)


class TaskRunner:
    def __init__(
        self,
        settings: Settings,
        sandbox_manager: SandboxManager,
        task_repo: TasksRepository,
        skill_repo: SkillsRepository,
        memory_repo: MemoryRepository,
        knowledge_repo: KnowledgeRepository,
        conversation_repo: ConversationsRepository,
        scheduled_repo: ScheduledTasksRepository | None = None,
    ) -> None:
        self.settings = settings
        self.sandbox = sandbox_manager
        self.task_repo = task_repo
        self.skill_repo = skill_repo
        self.memory_repo = memory_repo
        self.knowledge_repo = knowledge_repo
        self.conversation_repo = conversation_repo
        self.scheduled_repo = scheduled_repo
        self._active: dict[UUID, asyncio.Task] = {}

    def register(self, task_id: UUID, asyncio_task: asyncio.Task) -> None:
        self._active[task_id] = asyncio_task

    def cancel(self, task_id: UUID) -> bool:
        t = self._active.get(task_id)
        if t and not t.done():
            t.cancel()
            return True
        return False

    def cancel_all(self) -> int:
        """Cancel all active tasks. Returns number of tasks cancelled."""
        count = 0
        for task_id in list(self._active):
            if self.cancel(task_id):
                count += 1
        return count

    def active_task_ids(self) -> list[UUID]:
        return [tid for tid, t in self._active.items() if not t.done()]

    async def _build_context_prefix(
        self,
        user_id: int,
        chat_id: int,
        task_description: str = "",
        prompt_logger: PromptBlockLogger | None = None,
    ) -> tuple[str, list[MemoryEntry]]:
        parts: list[str] = []

        def _log(block: str, content: str) -> None:
            if prompt_logger:
                prompt_logger.log(block, content)

        # 0a. User deep settings
        settings_entries = await self.memory_repo.recall_by_prefix("_setting:", user_id)
        if settings_entries:
            lines = [f"- {e.key.removeprefix('_setting:')}: {e.content}" for e in settings_entries]
            parts.append("YOUR SETTINGS:\n" + "\n".join(lines))
            _log("settings", parts[-1])

        # 0b. Current date/time (feature toggle)
        if self.settings.feature_inject_datetime:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            parts.append(f"CURRENT DATE AND TIME: {now}")
            _log("datetime", parts[-1])

        # 1. Search relevant insights by task description (FTS)
        relevant: list = []
        if task_description:
            relevant = await self.memory_repo.search_by_prefix_fts(
                "_insight:", task_description, user_id, limit=10
            )

        # 2. Load recent insights only if FTS didn't find enough
        if len(relevant) < 5:
            recent_insights = await self.memory_repo.recall_by_prefix("_insight:", user_id)
            recent_insights = recent_insights[:3]
        else:
            recent_insights = []

        # 3. Merge and dedup (relevant first, then recent not yet included)
        seen_ids = {e.id for e in relevant}
        merged = list(relevant)
        for e in recent_insights:
            if e.id not in seen_ids:
                merged.append(e)
                seen_ids.add(e.id)

        insights = merged[:15]

        if insights:
            lines = [f"- {e.key.removeprefix('_insight:')}: {e.content}" for e in insights]
            parts.append("YOUR LEARNED INSIGHTS:\n" + "\n".join(lines))
            _log("insights", parts[-1])

        ctx = await self.memory_repo.recall_by_prefix("_ctx:", user_id)
        if ctx:
            lines = [f"- {e.key.removeprefix('_ctx:')}: {e.content}" for e in ctx]
            parts.append("PREVIOUS TASK CONTEXT:\n" + "\n".join(lines))
            _log("task_context", parts[-1])

        # Stored findings from previous tasks
        data_entries = await self.memory_repo.recall_by_prefix("_data:", user_id)
        if data_entries:
            lines = [
                f"- {e.key.removeprefix('_data:')}: {e.content[:300]}"
                for e in data_entries[:20]
            ]
            parts.append("STORED FINDINGS (from previous task):\n" + "\n".join(lines))
            _log("findings", parts[-1])

        # Recent conversation history
        recent_tasks = await self.task_repo.get_recent_completed(
            user_id, chat_id, limit=5
        )
        if recent_tasks:
            conv_lines: list[str] = []
            for t in recent_tasks:
                desc = (t.description or "")[:300]
                result = (t.result or "(no result)")[:500]
                status_label = t.status.value.upper()
                ts = t.created_at.strftime("%H:%M")
                conv_lines.append(
                    f"[{ts} | {status_label}]\nUser: {desc}\nYou: {result}"
                )
            parts.append(
                "RECENT CONVERSATION (last messages in this chat):\n"
                + "\n---\n".join(conv_lines)
            )
            _log("conversation", parts[-1])

        return "\n\n".join(parts), insights

    async def run(self, task: Task, transport: ChatTransport) -> None:
        prompt_logger = PromptBlockLogger(self.settings)
        prompt_logger.set_transport(transport, task.chat_id)

        try:
            await self.task_repo.update_status(task.id, TaskStatus.RUNNING)

            extra_tools: list = []
            system_prompt_addon = ""
            plan_state: PlanState | None = None

            prompts_mod = None
            if self.settings.feature_persistent_planning:
                plan_state = PlanState(
                    max_depth=self.settings.planning_decomposition_depth,
                    min_steps=self.settings.planning_min_steps,
                    max_steps=self.settings.planning_max_steps,
                )
                extra_tools.append(
                    make_show_plan_tool(transport, task.chat_id, plan_state)
                )
                prompts_mod = get_prompts(self.settings.prompt_language)
                system_prompt_addon = prompts_mod.PERSISTENT_PLANNING_ADDON

            if self.scheduled_repo is not None:
                if prompts_mod is None:
                    prompts_mod = get_prompts(self.settings.prompt_language)
                scheduling_text = prompts_mod.SCHEDULING_ADDON
                system_prompt_addon += scheduling_text
                prompt_logger.log("scheduling_addon", scheduling_text)

            agent = build_supervisor_agent(
                settings=self.settings,
                sandbox=self.sandbox,
                skill_repo=self.skill_repo,
                memory_repo=self.memory_repo,
                knowledge_repo=self.knowledge_repo,
                user_id=task.user_id,
                extra_tools=extra_tools or None,
                system_prompt_addon=system_prompt_addon,
                plan_state=plan_state,
                chat_id=task.chat_id,
                scheduled_repo=self.scheduled_repo,
            )

            callback = TransportProgressCallback(
                transport=transport, chat_id=task.chat_id, task_id=task.id
            )

            context_prefix, active_insights = await self._build_context_prefix(
                task.user_id, task.chat_id, task.description,
                prompt_logger=prompt_logger,
            )

            if active_insights and self.settings.feature_persistent_planning:
                insight_lines = "\n".join(
                    f"  \u2022 {transport.format_text(e.key.removeprefix('_insight:'))}"
                    for e in active_insights
                )
                try:
                    await transport.send_text(
                        task.chat_id,
                        f"\U0001f9e0 <b>Using {len(active_insights)} insights:</b>\n{insight_lines}",
                    )
                except Exception:
                    logger.debug("Failed to send insights message")

            agent_input = task.description
            if context_prefix:
                agent_input = f"{context_prefix}\n\n---\nUSER REQUEST: {task.description}"

            prompt_logger.log("user_request", agent_input)

            result = await agent.ainvoke(
                {"input": agent_input},
                config={
                    "callbacks": [callback],
                    "conversation_repo": self.conversation_repo,
                    "task_id": task.id,
                    "prompt_logger": prompt_logger,
                },
            )

            final = result.get("output", "No output.")

            is_failure = _is_failure_answer(final)
            task_status = TaskStatus.FAILED if is_failure else TaskStatus.COMPLETED

            await self.task_repo.update_status(
                task.id, task_status, result=final
            )

            issues = await validate_response(
                settings=self.settings,
                answer=final,
            )

            insights = await reflect_and_save(
                settings=self.settings,
                memory_repo=self.memory_repo,
                user_id=task.user_id,
                task_description=task.description,
                task_result=final,
                validation_issues=issues,
            )

            await self.memory_repo.delete_by_prefix("_ctx:", task.user_id)

            fmt = transport.format_text
            contradicted = [i for i in issues if i.get("verdict") == "contradicted"]
            if contradicted:
                corrections = "\n".join(
                    f"  \u274c {fmt(i['claim'])} \u2192 {fmt(i['correction'])}"
                    for i in contradicted if i.get("correction")
                )
                msg = f"\u26a0\ufe0f <b>Answer may contain inaccuracies:</b>\n{corrections}\n\n---\n\n{fmt(final)}"
            else:
                if is_failure:
                    msg = fmt(final)
                else:
                    msg = f"Task completed!\n\n{fmt(final)}"

            uncertain = [i for i in issues if i.get("verdict") == "uncertain"]
            if uncertain:
                lines = "\n".join(f"  \u2753 {fmt(i['claim'])}" for i in uncertain)
                msg += f"\n\n<i>Unverified claims:</i>\n{lines}"
            if insights:
                lines = "\n".join(
                    f"  \u2022 {fmt(i['key'])}: {fmt(i['content'])}"
                    for i in insights
                )
                msg += f"\n\n<b>Insights saved:</b>\n{lines}"
            try:
                await transport.send_text(task.chat_id, msg)
            except Exception:
                logger.warning("Failed to send result to chat %s", task.chat_id)

            # Post-task: check for stored findings and notify user
            try:
                data_entries = await self.memory_repo.recall_by_prefix(
                    "_data:", task.user_id
                )
                if data_entries:
                    summary_lines = [
                        f"  \u2022 {e.key.removeprefix('_data:')}: {e.content[:100]}"
                        for e in data_entries[:10]
                    ]
                    remaining = max(0, len(data_entries) - 10)
                    findings_msg = (
                        f"\U0001f4ca <b>Collected {len(data_entries)} findings:</b>\n"
                        + "\n".join(summary_lines)
                    )
                    if remaining:
                        findings_msg += f"\n  ... and {remaining} more"
                    findings_msg += (
                        "\n\n<i>Data saved. Send 'export to file' to save as JSON.</i>"
                    )
                    await transport.send_text(task.chat_id, findings_msg)
            except Exception:
                logger.debug("Failed to send findings summary")

        except asyncio.CancelledError:
            await self.task_repo.update_status(task.id, TaskStatus.CANCELLED)
            await transport.send_text(task.chat_id, "Task cancelled.")

        except Exception as e:
            logger.exception("Task %s failed", task.id)
            await self.task_repo.update_status(
                task.id, TaskStatus.FAILED, result=str(e)
            )
            try:
                await transport.send_text(
                    task.chat_id, f"Task failed: {transport.format_text(str(e)[:1000])}"
                )
            except Exception:
                pass

        finally:
            self._active.pop(task.id, None)
