from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.db.repositories.skills import SkillsRepository


class SearchSkillsInput(BaseModel):
    query: str = Field(description="Search query: keyword, skill name, or tag")


def make_search_skills_tool(skill_repo: SkillsRepository):
    @tool(args_schema=SearchSkillsInput)
    async def search_skills(query: str) -> str:
        """Search skills by name, description, or tags. Returns matching skills with their schemas."""
        skills = await skill_repo.search(query)
        if not skills:
            return f"No skills found for '{query}'."
        lines = []
        for s in skills:
            line = f"- {s.name}: {s.description}"
            if s.input_schema:
                line += f" | Input: {s.input_schema}"
            if s.output_schema:
                line += f" | Output: {s.output_schema}"
            lines.append(line)
        return "\n".join(lines)

    return search_skills
