from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import Message

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text & ~F.text.startswith("/"))
async def handle_chat(
    message: Message,
    **kwargs,
) -> None:
    """Handle plain text messages — route to agent as a task."""
    from src.bot.handlers.code import start_task

    await start_task(
        description=message.text or "",
        message=message,
        **kwargs,
    )
