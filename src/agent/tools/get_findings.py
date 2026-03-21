from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain_core.tools import tool

if TYPE_CHECKING:
    from src.db.repositories.memory import MemoryRepository

logger = logging.getLogger(__name__)


def make_get_findings_tool(memory_repo: MemoryRepository, user_id: int):
    @tool
    async def get_findings() -> str:
        """Retrieve all stored findings from the current and previous sessions."""
        entries = await memory_repo.recall_by_prefix("_data:", user_id)
        if not entries:
            return "No findings stored yet."
        lines = [
            f"- {e.key.removeprefix('_data:')}: {e.content[:500]}"
            for e in entries
        ]
        return f"Stored findings ({len(entries)}):\n" + "\n".join(lines)

    return get_findings
