from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class ChatTransport(Protocol):
    """Transport-agnostic interface for sending messages to users."""

    async def send_text(
        self, chat_id: int, text: str, *, parse_mode: str | None = None
    ) -> None:
        """Send a text message (handles splitting/escaping internally)."""
        ...

    async def send_progress(
        self, chat_id: int, task_id: UUID, step: int, status: str
    ) -> None:
        """Send a progress update for a running task."""
        ...

    async def send_error(
        self, chat_id: int, task_id: UUID, step: int, error: str
    ) -> None:
        """Send an error notification for a task step."""
        ...

    async def send_prompt_block(
        self, chat_id: int, block_name: str, content: str
    ) -> None:
        """Broadcast a prompt block (no-op for Telegram, WS event for web)."""
        ...

    def format_text(self, text: str) -> str:
        """Escape text for this transport's output format."""
        ...

    def split_message(self, text: str) -> list[str]:
        """Split a long message into transport-appropriate chunks."""
        ...
