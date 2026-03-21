from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from src.db.models import TaskCreate
from src.db.repositories.scheduled_tasks import ScheduledTasksRepository
from src.db.repositories.tasks import TasksRepository

if TYPE_CHECKING:
    from src.services.task_runner import TaskRunner
    from src.transport.protocol import ChatTransport

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 60


class Scheduler:
    def __init__(
        self,
        scheduled_repo: ScheduledTasksRepository,
        task_repo: TasksRepository,
        task_runner: TaskRunner,
        transport: ChatTransport,
    ) -> None:
        self._scheduled_repo = scheduled_repo
        self._task_repo = task_repo
        self._task_runner = task_runner
        self._transport = transport

    async def run_forever(self) -> None:
        logger.info("Scheduler started (poll every %ds)", POLL_INTERVAL_SECONDS)
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                logger.info("Scheduler stopped")
                return
            except Exception:
                logger.exception("Scheduler tick error")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def _tick(self) -> None:
        due = await self._scheduled_repo.get_due()
        if not due:
            return
        logger.info("Scheduler: %d due tasks", len(due))
        for st in due:
            await self._dispatch(st)

    async def _dispatch(self, st) -> None:
        # Mark running first to prevent double-dispatch
        await self._scheduled_repo.mark_running(st.id)

        task_create = TaskCreate(
            user_id=st.user_id,
            chat_id=st.chat_id,
            description=f"[Scheduled #{st.id}] {st.description}",
        )
        task = await self._task_repo.create(task_create)

        try:
            await self._transport.send_text(
                st.chat_id,
                f"Scheduled task #{st.id} starting: {st.description[:200]}",
            )
        except Exception:
            logger.debug("Failed to notify user about scheduled task %d", st.id)

        asyncio_task = asyncio.create_task(
            self._run_and_record(st.id, task, st.chat_id)
        )
        self._task_runner.register(task.id, asyncio_task)

    async def _run_and_record(self, st_id: int, task, chat_id: int) -> None:
        try:
            await self._task_runner.run(task, self._transport)
            # Fetch updated task to get result
            updated = await self._task_repo.get_by_id(task.id)
            result = (updated.result or "completed") if updated else "completed"
            await self._scheduled_repo.set_last_result(st_id, result)
        except Exception as e:
            logger.exception("Scheduled task %d execution failed", st_id)
            await self._scheduled_repo.set_last_result(st_id, f"Error: {e}")
