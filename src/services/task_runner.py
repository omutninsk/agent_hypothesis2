from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from aiogram import Bot

from src.agent.callbacks import TelegramProgressCallback
from src.agent.prompts import PERSISTENT_PLANNING_ADDON
from src.agent.supervisor import build_supervisor_agent
from src.agent.tools.show_plan import make_show_plan_tool
from src.bot.formatters import escape, split_message
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
    ) -> None:
        self.settings = settings
        self.sandbox = sandbox_manager
        self.task_repo = task_repo
        self.skill_repo = skill_repo
        self.memory_repo = memory_repo
        self.knowledge_repo = knowledge_repo
        self.conversation_repo = conversation_repo
        self._active: dict[UUID, asyncio.Task] = {}

    def register(self, task_id: UUID, asyncio_task: asyncio.Task) -> None:
        self._active[task_id] = asyncio_task

    def cancel(self, task_id: UUID) -> bool:
        t = self._active.get(task_id)
        if t and not t.done():
            t.cancel()
            return True
        return False

    async def _build_context_prefix(
        self, user_id: int, chat_id: int, task_description: str = ""
    ) -> tuple[str, list[MemoryEntry]]:
        parts: list[str] = []

        # 1. Search relevant insights by task description (FTS)
        relevant: list = []
        if task_description:
            relevant = await self.memory_repo.search_by_prefix_fts(
                "_insight:", task_description, user_id, limit=10
            )

        # 2. Also load 5 most recent insights (recency signal)
        recent_insights = await self.memory_repo.recall_by_prefix("_insight:", user_id)
        recent_insights = recent_insights[:5]

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

        ctx = await self.memory_repo.recall_by_prefix("_ctx:", user_id)
        if ctx:
            lines = [f"- {e.key.removeprefix('_ctx:')}: {e.content}" for e in ctx]
            parts.append("PREVIOUS TASK CONTEXT:\n" + "\n".join(lines))

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

        return "\n\n".join(parts), insights

    async def run(self, task: Task, bot: Bot) -> None:
        try:
            await self.task_repo.update_status(task.id, TaskStatus.RUNNING)

            extra_tools: list = []
            system_prompt_addon = ""

            if self.settings.feature_persistent_planning:
                extra_tools.append(make_show_plan_tool(bot, task.chat_id))
                system_prompt_addon = PERSISTENT_PLANNING_ADDON

            agent = build_supervisor_agent(
                settings=self.settings,
                sandbox=self.sandbox,
                skill_repo=self.skill_repo,
                memory_repo=self.memory_repo,
                knowledge_repo=self.knowledge_repo,
                user_id=task.user_id,
                extra_tools=extra_tools or None,
                system_prompt_addon=system_prompt_addon,
            )

            callback = TelegramProgressCallback(
                bot=bot, chat_id=task.chat_id, task_id=task.id
            )

            context_prefix, active_insights = await self._build_context_prefix(
                task.user_id, task.chat_id, task.description
            )

            if active_insights and self.settings.feature_persistent_planning:
                insight_lines = "\n".join(
                    f"  \u2022 {escape(e.key.removeprefix('_insight:'))}"
                    for e in active_insights
                )
                try:
                    await bot.send_message(
                        task.chat_id,
                        f"\U0001f9e0 <b>Using {len(active_insights)} insights:</b>\n{insight_lines}",
                    )
                except Exception:
                    logger.debug("Failed to send insights message")

            agent_input = task.description
            if context_prefix:
                agent_input = f"{context_prefix}\n\n---\nUSER REQUEST: {task.description}"

            result = await agent.ainvoke(
                {"input": agent_input},
                config={
                    "callbacks": [callback],
                    "conversation_repo": self.conversation_repo,
                    "task_id": task.id,
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

            contradicted = [i for i in issues if i.get("verdict") == "contradicted"]
            if contradicted:
                corrections = "\n".join(
                    f"  \u274c {escape(i['claim'])} \u2192 {escape(i['correction'])}"
                    for i in contradicted if i.get("correction")
                )
                msg = f"\u26a0\ufe0f <b>Answer may contain inaccuracies:</b>\n{corrections}\n\n---\n\n{escape(final)}"
            else:
                if is_failure:
                    msg = escape(final)
                else:
                    msg = f"Task completed!\n\n{escape(final)}"

            uncertain = [i for i in issues if i.get("verdict") == "uncertain"]
            if uncertain:
                lines = "\n".join(f"  \u2753 {escape(i['claim'])}" for i in uncertain)
                msg += f"\n\n<i>Unverified claims:</i>\n{lines}"
            if insights:
                lines = "\n".join(
                    f"  \u2022 {escape(i['key'])}: {escape(i['content'])}"
                    for i in insights
                )
                msg += f"\n\n<b>Insights saved:</b>\n{lines}"
            try:
                for chunk in split_message(msg):
                    await bot.send_message(task.chat_id, chunk)
            except Exception:
                logger.warning("Failed to send result to chat %s", task.chat_id)

        except asyncio.CancelledError:
            await self.task_repo.update_status(task.id, TaskStatus.CANCELLED)
            await bot.send_message(task.chat_id, "Task cancelled.")

        except Exception as e:
            logger.exception("Task %s failed", task.id)
            await self.task_repo.update_status(
                task.id, TaskStatus.FAILED, result=str(e)
            )
            try:
                await bot.send_message(
                    task.chat_id, f"Task failed: {escape(str(e)[:1000])}"
                )
            except Exception:
                pass

        finally:
            self._active.pop(task.id, None)
