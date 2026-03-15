from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.db.repositories.knowledge import KnowledgeRepository


class SearchKnowledgeInput(BaseModel):
    query: str = Field(description="Search query to find relevant knowledge entries")


def make_search_knowledge_tool(knowledge_repo: KnowledgeRepository, user_id: int):
    @tool(args_schema=SearchKnowledgeInput)
    async def search_knowledge(query: str) -> str:
        """Search previously saved knowledge and research results. Use before starting research to check existing data."""
        entries = await knowledge_repo.search(query=query, user_id=user_id)
        if not entries:
            return "No knowledge found."

        lines = []
        for e in entries:
            src = f" (source: {e.source})" if e.source else ""
            ts = e.created_at.strftime("%Y-%m-%d %H:%M")
            lines.append(f"[{e.topic}] {e.content}{src} — {ts}")
        return "\n".join(lines)

    return search_knowledge
