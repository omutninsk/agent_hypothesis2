from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.bot.formatters import escape, split_message
from src.db.repositories.memory import MemoryRepository

router = Router()
logger = logging.getLogger(__name__)


def _format_entries(entries: list, header: str) -> str:
    if not entries:
        return ""
    lines = [f"<b>— {header} —</b>"]
    for e in entries:
        date = e.updated_at.strftime("%Y-%m-%d %H:%M")
        display_key = e.key.split(":", 1)[-1] if ":" in e.key else e.key
        lines.append(f"<b>{escape(display_key)}</b> — {escape(e.content[:200])}\n<i>{date}</i>")
    return "\n\n".join(lines)


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

    ctx_entries = [e for e in entries if e.key.startswith("_ctx:")]
    insight_entries = [e for e in entries if e.key.startswith("_insight:")]
    user_entries = [
        e for e in entries
        if not e.key.startswith(("_ctx:", "_insight:", "_setting:"))
    ]

    sections = [
        _format_entries(ctx_entries, "Active Task Context"),
        _format_entries(insight_entries, "Agent Insights"),
        _format_entries(user_entries, "User Memories"),
    ]
    text = "\n\n".join(s for s in sections if s)

    for chunk in split_message(text):
        await message.reply(chunk)
