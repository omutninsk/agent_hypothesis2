from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain_core.tools import tool
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from src.db.repositories.memory import MemoryRepository

logger = logging.getLogger(__name__)

_MAX_FINDINGS = 50
_WARN_THRESHOLD = 40


class StoreFindingInput(BaseModel):
    key: str = Field(description="Short label, e.g. 'news_1', 'price_gpu_rtx4090'")
    content: str = Field(description="The data/finding to store")


def make_store_finding_tool(memory_repo: MemoryRepository, user_id: int):
    @tool(args_schema=StoreFindingInput)
    async def store_finding(key: str, content: str) -> str:
        """Store a data finding for later use. Persists throughout the task and across tasks."""
        existing = await memory_repo.recall_by_prefix("_data:", user_id)
        count = len(existing)

        if count >= _MAX_FINDINGS:
            return (
                f"Cannot store: limit of {_MAX_FINDINGS} findings reached. "
                f"Use get_findings to review stored data, or export_findings to save to file."
            )

        await memory_repo.save(f"_data:{key}", content, user_id)
        count += 1

        msg = f"Finding stored: '{key}' (total: {count})"
        if count >= _WARN_THRESHOLD:
            msg += f" — approaching limit ({_MAX_FINDINGS}). Consider exporting soon."
        return msg

    return store_finding
