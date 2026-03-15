from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from aiogram import Bot
from langchain_core.callbacks import AsyncCallbackHandler

from src.bot.formatters import escape

logger = logging.getLogger(__name__)

_STATUS_MAP = {
    "write_file": "Writing file",
    "read_file": "Reading file",
    "execute_code": "Executing code",
    "save_skill": "Saving skill",
    "list_skills": "Listing skills",
    "run_skill": "Running skill",
    "search_skills": "Searching skills",
    "run_existing_skill": "Running existing skill",
    "delegate_to_coder": "Delegating to coder agent",
    "save_to_memory": "Saving to memory",
    "recall_memory": "Recalling memory",
}


class TelegramProgressCallback(AsyncCallbackHandler):
    def __init__(self, bot: Bot, chat_id: int, task_id: UUID) -> None:
        self.bot = bot
        self.chat_id = chat_id
        self.task_id = task_id
        self._step = 0

    async def on_tool_start(
        self, serialized: dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        self._step += 1
        name = serialized.get("name", "unknown")
        status = _STATUS_MAP.get(name, f"Using {name}")
        try:
            await self.bot.send_message(
                self.chat_id, f"[Step {self._step}] {status}..."
            )
        except Exception:
            logger.debug("Failed to send progress update")

    async def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        try:
            await self.bot.send_message(
                self.chat_id,
                f"[Step {self._step}] Error: {escape(str(error)[:500])}",
            )
        except Exception:
            pass
