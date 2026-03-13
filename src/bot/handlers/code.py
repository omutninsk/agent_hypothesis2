from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message

from src.db.models import TaskCreate
from src.db.repositories.tasks import TasksRepository
from src.services.task_runner import TaskRunner

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("code"))
async def handle_code(
    message: Message,
    bot: Bot,
    task_runner: TaskRunner,
    task_repo: TasksRepository,
) -> None:
    """Handle /code <description> — start a coding task."""
    description = (message.text or "").removeprefix("/code").strip()
    if not description:
        await message.reply("Usage: /code &lt;task description&gt;")
        return

    task = await task_repo.create(
        TaskCreate(
            user_id=message.from_user.id,  # type: ignore[union-attr]
            chat_id=message.chat.id,
            description=description,
        )
    )

    await message.reply(f"Task started. ID: <code>{task.id}</code>")

    bg = asyncio.create_task(
        task_runner.run(task=task, bot=bot),
        name=f"task-{task.id}",
    )
    task_runner.register(task.id, bg)
