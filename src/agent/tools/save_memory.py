from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.db.repositories.memory import MemoryRepository


class SaveMemoryInput(BaseModel):
    key: str = Field(description="Memory key, e.g. 'user_preferences', 'plans', 'insights'")
    content: str = Field(description="Content to remember")


def make_save_memory_tool(memory_repo: MemoryRepository, user_id: int):
    @tool(args_schema=SaveMemoryInput)
    async def save_to_memory(key: str, content: str) -> str:
        """Save information to persistent memory. Use for plans, user preferences, insights, conversation context."""
        entry = await memory_repo.save(key=key, content=content, user_id=user_id)
        return f"Saved to memory: '{key}' (updated_at={entry.updated_at})"

    return save_to_memory
