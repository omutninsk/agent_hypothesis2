from __future__ import annotations

from langchain_core.tools import tool

from src.db.repositories.skills import SkillsRepository


def make_list_skills_tool(skill_repo: SkillsRepository):
    @tool
    async def list_skills() -> str:
        """List all saved skills."""
        skills = await skill_repo.list_all()
        if not skills:
            return "No skills saved yet."
        lines = [f"- {s.name}: {s.description}" for s in skills]
        return "\n".join(lines)

    return list_skills
