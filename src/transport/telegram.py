from __future__ import annotations

import logging
from uuid import UUID

from aiogram import Bot

from src.bot.formatters import escape, split_message as tg_split

logger = logging.getLogger(__name__)


class TelegramTransport:
    """ChatTransport implementation backed by aiogram Bot."""

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    @property
    def bot(self) -> Bot:
        """Access the underlying Bot for Telegram-specific operations."""
        return self._bot

    async def send_text(
        self, chat_id: int, text: str, *, parse_mode: str | None = None
    ) -> None:
        for chunk in self.split_message(text):
            await self._bot.send_message(chat_id, chunk, parse_mode=parse_mode)

    async def send_progress(
        self, chat_id: int, task_id: UUID, step: int, status: str
    ) -> None:
        try:
            await self._bot.send_message(chat_id, f"[Step {step}] {status}...")
        except Exception:
            logger.debug("Failed to send progress update")

    async def send_error(
        self, chat_id: int, task_id: UUID, step: int, error: str
    ) -> None:
        try:
            await self._bot.send_message(
                chat_id, f"[Step {step}] Error: {escape(error[:500])}"
            )
        except Exception:
            pass

    async def send_prompt_block(
        self, chat_id: int, block_name: str, content: str
    ) -> None:
        pass  # no-op for Telegram

    def format_text(self, text: str) -> str:
        return escape(text)

    def split_message(self, text: str) -> list[str]:
        return tg_split(text)
