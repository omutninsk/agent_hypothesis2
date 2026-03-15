from __future__ import annotations

import os
import shutil

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.db.repositories.skills import SkillsRepository


class DeleteSkillInput(BaseModel):
    name: str = Field(description="Name of the skill to delete")


def make_delete_skill_tool(skill_repo: SkillsRepository, skills_dir: str):
    @tool(args_schema=DeleteSkillInput)
    async def delete_skill(name: str) -> str:
        """Delete a broken or duplicate skill by name. Removes from database and disk."""
        skill = await skill_repo.get_by_name(name)
        if not skill:
            return f"Skill '{name}' not found."

        await skill_repo.delete(skill.id)

        skill_path = os.path.join(skills_dir, name)
        if os.path.isdir(skill_path):
            shutil.rmtree(skill_path, ignore_errors=True)

        return f"Skill '{name}' deleted successfully."

    return delete_skill
