from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.db.repositories.memory import MemoryRepository


class RecallMemoryInput(BaseModel):
    query: str = Field(description="Memory key or search query to find relevant memories")


def make_recall_memory_tool(memory_repo: MemoryRepository, user_id: int):
    @tool(args_schema=RecallMemoryInput)
    async def recall_memory(query: str) -> str:
        """Recall information from persistent memory. Search by key or keyword."""
        # Try exact key match first
        entry = await memory_repo.recall(key=query, user_id=user_id)
        if entry:
            return f"[{entry.key}] {entry.content} (updated: {entry.updated_at})"

        # Fall back to search
        entries = await memory_repo.search(query=query, user_id=user_id)
        if not entries:
            return "No memories found."

        lines = []
        for e in entries:
            lines.append(f"[{e.key}] {e.content} (updated: {e.updated_at})")
        return "\n".join(lines)

    return recall_memory
