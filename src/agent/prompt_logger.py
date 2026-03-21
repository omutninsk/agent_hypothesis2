from __future__ import annotations

import logging

from src.config import Settings

_logger = logging.getLogger("prompt_blocks")
_SEP = "=" * 60

_ALL_BLOCKS = frozenset({
    "system", "tool_descriptions", "planning_addon",
    "settings", "datetime", "insights", "task_context",
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

    def log(self, block: str, content: str) -> None:
        if not self._active or block not in self._enabled:
            return
        _logger.debug(
            "\n%s\n[PROMPT BLOCK: %s] (%d chars)\n%s\n%s\n%s",
            _SEP, block.upper(), len(content), _SEP, content, _SEP,
        )

    def log_response(self, iteration: int, content: str) -> None:
        if not self._active or "response" not in self._enabled:
            return
        _logger.debug(
            "\n%s\n[LLM RESPONSE iter=%d] (%d chars)\n%s\n%s\n%s",
            _SEP, iteration, len(content), _SEP, content, _SEP,
        )
