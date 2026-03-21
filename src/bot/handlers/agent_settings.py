from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.bot.formatters import escape
from src.db.repositories.memory import MemoryRepository

router = Router()
logger = logging.getLogger(__name__)

_PREFIX = "_setting:"


@router.message(Command("settings"))
async def handle_settings(
    message: Message,
    memory_repo: MemoryRepository,
) -> None:
    """Handle /settings — manage agent deep settings."""
    user_id = message.from_user.id  # type: ignore[union-attr]
    raw = (message.text or "").strip()

    # Strip the command itself
    parts = raw.split(maxsplit=1)
    args = parts[1] if len(parts) > 1 else ""

    if not args:
        await _show_settings(message, memory_repo, user_id)
        return

    tokens = args.split(maxsplit=2)
    subcmd = tokens[0].lower()

    if subcmd == "set":
        if len(tokens) < 3:
            await message.reply("Usage: /settings set &lt;key&gt; &lt;value&gt;")
            return
        key = tokens[1]
        value = tokens[2]
        await memory_repo.save(f"{_PREFIX}{key}", value, user_id)
        await message.reply(f"Setting <b>{escape(key)}</b> saved.")

    elif subcmd == "del":
        if len(tokens) < 2:
            await message.reply("Usage: /settings del &lt;key&gt;")
            return
        key = tokens[1]
        deleted = await memory_repo.delete(f"{_PREFIX}{key}", user_id)
        if deleted:
            await message.reply(f"Setting <b>{escape(key)}</b> deleted.")
        else:
            await message.reply(f"Setting <b>{escape(key)}</b> not found.")

    else:
        await message.reply(
            "Unknown subcommand. Use:\n"
            "/settings — show all\n"
            "/settings set &lt;key&gt; &lt;value&gt;\n"
            "/settings del &lt;key&gt;"
        )


async def _show_settings(
    message: Message,
    memory_repo: MemoryRepository,
    user_id: int,
) -> None:
    entries = await memory_repo.recall_by_prefix(_PREFIX, user_id)
    if not entries:
        await message.reply(
            "No settings configured. Use /settings set &lt;key&gt; &lt;value&gt; to add one."
        )
        return

    lines = ["<b>— Agent Settings —</b>"]
    for e in entries:
        display_key = e.key.removeprefix(_PREFIX)
        date = e.updated_at.strftime("%Y-%m-%d %H:%M")
        lines.append(
            f"<b>{escape(display_key)}</b> — {escape(e.content[:200])}\n<i>{date}</i>"
        )
    await message.reply("\n\n".join(lines))
