from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class WebSearchInput(BaseModel):
    query: str = Field(description="Search query")
    max_results: int = Field(default=5, description="Max results to return")


def make_web_search_tool():
    @tool(args_schema=WebSearchInput)
    async def web_search(query: str, max_results: int = 5) -> str:
        """Search the web using DuckDuckGo. Use to research APIs, find solutions, check documentation before coding."""
        from duckduckgo_search import DDGS

        results = DDGS().text(query, max_results=max_results)
        lines = []
        for r in results:
            lines.append(f"**{r['title']}**\n{r['href']}\n{r['body']}")
        return "\n\n".join(lines) if lines else "No results found."

    return web_search
