from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.bot.formatters import escape
from src.db.repositories.memory import MemoryRepository

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("memory"))
async def handle_memory(
    message: Message,
    memory_repo: MemoryRepository,
) -> None:
    """Handle /memory — show all agent memories for this user."""
    user_id = message.from_user.id  # type: ignore[union-attr]
    entries = await memory_repo.recall_all(user_id=user_id)

    if not entries:
        await message.reply("No memories stored yet.")
        return

    lines = []
    for e in entries:
        date = e.updated_at.strftime("%Y-%m-%d %H:%M")
        lines.append(f"<b>{escape(e.key)}</b> — {escape(e.content[:200])}\n<i>{date}</i>")

    text = "\n\n".join(lines)
    # Telegram message limit is 4096 chars
    if len(text) > 4000:
        text = text[:4000] + "\n\n... (truncated)"

    await message.reply(text)
