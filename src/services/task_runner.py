from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from aiogram import Bot

from src.agent.callbacks import TelegramProgressCallback
from src.agent.supervisor import build_supervisor_agent
from src.bot.formatters import escape
from src.config import Settings
from src.db.models import Task, TaskStatus
from src.db.repositories.knowledge import KnowledgeRepository
from src.db.repositories.memory import MemoryRepository
from src.db.repositories.skills import SkillsRepository
from src.db.repositories.conversations import ConversationsRepository
from src.db.repositories.tasks import TasksRepository
from src.sandbox.manager import SandboxManager
logger = logging.getLogger(__name__)


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

    async def _build_context_prefix(self, user_id: int) -> str:
        parts: list[str] = []

        insights = await self.memory_repo.recall_by_prefix("_insight:", user_id)
        if insights:
            lines = [f"- {e.key.removeprefix('_insight:')}: {e.content}" for e in insights[:20]]
            parts.append("YOUR LEARNED INSIGHTS:\n" + "\n".join(lines))

        ctx = await self.memory_repo.recall_by_prefix("_ctx:", user_id)
        if ctx:
            lines = [f"- {e.key.removeprefix('_ctx:')}: {e.content}" for e in ctx]
            parts.append("PREVIOUS TASK CONTEXT:\n" + "\n".join(lines))

        return "\n\n".join(parts)

    async def run(self, task: Task, bot: Bot) -> None:
        try:
            await self.task_repo.update_status(task.id, TaskStatus.RUNNING)

            agent = build_supervisor_agent(
                settings=self.settings,
                sandbox=self.sandbox,
                skill_repo=self.skill_repo,
                memory_repo=self.memory_repo,
                knowledge_repo=self.knowledge_repo,
                user_id=task.user_id,
            )

            callback = TelegramProgressCallback(
                bot=bot, chat_id=task.chat_id, task_id=task.id
            )

            context_prefix = await self._build_context_prefix(task.user_id)
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

            await self.task_repo.update_status(
                task.id, TaskStatus.COMPLETED, result=final
            )
            await self.memory_repo.delete_by_prefix("_ctx:", task.user_id)
            await bot.send_message(
                task.chat_id,
                f"Task completed!\n\n{escape(final[:3500])}",
            )

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
