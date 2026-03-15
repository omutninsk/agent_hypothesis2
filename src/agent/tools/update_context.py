from __future__ import annotations

from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.db.repositories.memory import MemoryRepository


class UpdateContextInput(BaseModel):
    layer: Literal["task", "insight"] = Field(
        description="'task' for current task progress (auto-cleared on completion), 'insight' for permanent self-knowledge",
    )
    key: str = Field(description="Context key, e.g. 'goal', 'step', 'weather_api'")
    content: str = Field(description="Content to save")


def make_update_context_tool(memory_repo: MemoryRepository, user_id: int):
    @tool(args_schema=UpdateContextInput)
    async def update_context(layer: str, key: str, content: str) -> str:
        """Update working memory.
        layer='task': current task progress (auto-cleared on completion).
        layer='insight': permanent self-knowledge (persists forever)."""
        full_key = f"_ctx:{key}" if layer == "task" else f"_insight:{key}"
        await memory_repo.save(key=full_key, content=content, user_id=user_id)
        label = "Task context" if layer == "task" else "Insight"
        return f"{label} saved: '{key}'"

    return update_context
