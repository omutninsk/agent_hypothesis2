from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.bot.formatters import escape
from src.db.models import TaskStatus
from src.db.repositories.tasks import TasksRepository
from src.services.task_runner import TaskRunner

router = Router()


@router.message(Command("status"))
async def handle_status(
    message: Message, task_repo: TasksRepository
) -> None:
    tasks = await task_repo.get_active_by_user(message.from_user.id)  # type: ignore[union-attr]
    if not tasks:
        await message.reply("No active tasks.")
        return
    lines = []
    for t in tasks:
        lines.append(
            f"<code>{t.id}</code> [{t.status.value}] "
            f"iter {t.iteration}/{t.max_iterations}\n"
            f"{escape(t.description[:200])}"
        )
    await message.reply("\n\n".join(lines))


@router.message(Command("stop"))
async def handle_stop(
    message: Message,
    task_repo: TasksRepository,
    task_runner: TaskRunner,
) -> None:
    tasks = await task_repo.get_active_by_user(message.from_user.id)  # type: ignore[union-attr]
    if not tasks:
        await message.reply("No active tasks to stop.")
        return

    cancelled = []
    for t in tasks:
        if task_runner.cancel(t.id):
            await task_repo.update_status(t.id, TaskStatus.CANCELLED)
            cancelled.append(str(t.id))

    if cancelled:
        await message.reply(f"Cancelled: {', '.join(cancelled)}")
    else:
        await message.reply("No tasks were running.")
