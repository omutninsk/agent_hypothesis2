from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from aiogram import Bot

from src.agent.callbacks import TelegramProgressCallback
from src.agent.core import build_agent
from src.bot.formatters import escape
from src.config import Settings
from src.db.models import Task, TaskStatus
from src.db.repositories.skills import SkillsRepository
from src.db.repositories.tasks import TasksRepository
from src.sandbox.manager import SandboxManager
from src.sandbox.workspace import WorkspaceManager

logger = logging.getLogger(__name__)


class TaskRunner:
    def __init__(
        self,
        settings: Settings,
        sandbox_manager: SandboxManager,
        workspace_manager: WorkspaceManager,
        task_repo: TasksRepository,
        skill_repo: SkillsRepository,
    ) -> None:
        self.settings = settings
        self.sandbox = sandbox_manager
        self.workspaces = workspace_manager
        self.task_repo = task_repo
        self.skill_repo = skill_repo
        self._active: dict[UUID, asyncio.Task] = {}

    def register(self, task_id: UUID, asyncio_task: asyncio.Task) -> None:
        self._active[task_id] = asyncio_task

    def cancel(self, task_id: UUID) -> bool:
        t = self._active.get(task_id)
        if t and not t.done():
            t.cancel()
            return True
        return False

    async def run(self, task: Task, bot: Bot) -> None:
        workspace = self.workspaces.create(str(task.id))

        try:
            await self.task_repo.update_status(task.id, TaskStatus.RUNNING)

            agent = build_agent(
                settings=self.settings,
                sandbox=self.sandbox,
                skill_repo=self.skill_repo,
                workspace_path=workspace,
                user_id=task.user_id,
            )

            callback = TelegramProgressCallback(
                bot=bot, chat_id=task.chat_id, task_id=task.id
            )

            result = await agent.ainvoke(
                {"input": task.description},
                config={"callbacks": [callback]},
            )

            final = result.get("output", "No output.")

            await self.task_repo.update_status(
                task.id, TaskStatus.COMPLETED, result=final
            )
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
            self.workspaces.destroy(str(task.id))
            self._active.pop(task.id, None)
