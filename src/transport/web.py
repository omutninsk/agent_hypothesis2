from __future__ import annotations

import html
import logging
from uuid import UUID

from src.transport.manager import ConnectionManager

logger = logging.getLogger(__name__)


class WebTransport:
    """ChatTransport implementation backed by WebSocket via ConnectionManager."""

    def __init__(self, manager: ConnectionManager) -> None:
        self._manager = manager

    async def send_text(
        self, chat_id: int, text: str, *, parse_mode: str | None = None
    ) -> None:
        await self._manager.send_to_chat(chat_id, {
            "type": "message",
            "text": text,
        })

    async def send_progress(
        self, chat_id: int, task_id: UUID, step: int, status: str
    ) -> None:
        await self._manager.send_to_chat(chat_id, {
            "type": "progress",
            "task_id": str(task_id),
            "step": step,
            "status": status,
        })

    async def send_error(
        self, chat_id: int, task_id: UUID, step: int, error: str
    ) -> None:
        await self._manager.send_to_chat(chat_id, {
            "type": "error",
            "task_id": str(task_id),
            "step": step,
            "error": error,
        })

    async def send_prompt_block(
        self, chat_id: int, block_name: str, content: str
    ) -> None:
        await self._manager.send_to_chat(chat_id, {
            "type": "prompt_block",
            "block": block_name,
            "content": content,
        })

    def format_text(self, text: str) -> str:
        return html.escape(text)

    def split_message(self, text: str) -> list[str]:
        return [text]
