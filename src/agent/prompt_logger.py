from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from src.config import Settings

if TYPE_CHECKING:
    from src.transport.protocol import ChatTransport

_logger = logging.getLogger("prompt_blocks")
_SEP = "=" * 60

_ALL_BLOCKS = frozenset({
    "system", "tool_descriptions", "planning_addon", "scheduling_addon",
    "settings", "datetime", "insights", "task_context", "findings",
    "conversation", "user_request", "full_prompt", "response",
})


class PromptBlockLogger:

    def __init__(self, settings: Settings) -> None:
        enabled = settings.log_prompt_blocks
        if "all" in enabled:
            self._enabled: frozenset[str] = _ALL_BLOCKS
        else:
            self._enabled = frozenset(enabled)
        self._active = bool(self._enabled)
        self._transport: ChatTransport | None = None
        self._chat_id: int | None = None

    def set_transport(self, transport: ChatTransport, chat_id: int) -> None:
        self._transport = transport
        self._chat_id = chat_id

    def _broadcast(self, block: str, content: str) -> None:
        if self._transport and self._chat_id is not None:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    self._transport.send_prompt_block(self._chat_id, block, content)
                )
            except RuntimeError:
                pass  # no event loop — skip broadcast

    def log(self, block: str, content: str) -> None:
        # Broadcast to web transport (always, regardless of log settings)
        self._broadcast(block, content)

        if not self._active or block not in self._enabled:
            return
        _logger.debug(
            "\n%s\n[PROMPT BLOCK: %s] (%d chars)\n%s\n%s\n%s",
            _SEP, block.upper(), len(content), _SEP, content, _SEP,
        )

    def log_response(self, iteration: int, content: str) -> None:
        # Broadcast response to web transport
        self._broadcast(f"response_iter_{iteration}", content)

        if not self._active or "response" not in self._enabled:
            return
        _logger.debug(
            "\n%s\n[LLM RESPONSE iter=%d] (%d chars)\n%s\n%s\n%s",
            _SEP, iteration, len(content), _SEP, content, _SEP,
        )
