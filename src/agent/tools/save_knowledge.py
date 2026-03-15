from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.db.repositories.knowledge import KnowledgeRepository


class SaveKnowledgeInput(BaseModel):
    topic: str = Field(description="Short label for the knowledge, e.g. 'weather_moscow', 'python_asyncio'")
    content: str = Field(description="The actual data or facts to save")
    source: str = Field(default="agent", description="Where the data came from, e.g. 'web_search', 'skill:weather'")


def make_save_knowledge_tool(knowledge_repo: KnowledgeRepository, user_id: int):
    @tool(args_schema=SaveKnowledgeInput)
    async def save_knowledge(topic: str, content: str, source: str = "agent") -> str:
        """Save a fact or data to the knowledge store for later search. Use after web_search or skill runs with useful findings."""
        entry = await knowledge_repo.save(
            topic=topic, content=content, user_id=user_id, source=source
        )
        return f"Saved knowledge #{entry.id}: '{entry.topic}' (source={entry.source})"

    return save_knowledge
