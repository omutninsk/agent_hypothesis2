from __future__ import annotations

import json
import os

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.db.models import SkillCreate
from src.db.repositories.skills import SkillsRepository


class SaveSkillInput(BaseModel):
    name: str = Field(description="Snake_case skill name, e.g. 'parse_csv'")
    description: str = Field(description="Short description of what the skill does")
    entry_point: str = Field(default="main.py", description="Main file to execute")
    dependencies: list[str] = Field(default=[], description="pip packages needed")
    proto_schema: str = Field(
        default="",
        description="Proto-style schema, e.g. 'message Input { string url = 1; } message Output { string text = 1; }'",
    )
    input_schema: dict = Field(
        default={},
        description='JSON Schema for input, e.g. {"type":"object","properties":{"url":{"type":"string"}}}',
    )
    output_schema: dict = Field(
        default={},
        description='JSON Schema for output, e.g. {"type":"object","properties":{"text":{"type":"string"}}}',
    )


def make_save_skill_tool(
    skill_repo: SkillsRepository, workspace_path: str, user_id: int
):
    @tool(args_schema=SaveSkillInput)
    async def save_skill(
        name: str,
        description: str,
        entry_point: str = "main.py",
        dependencies: list[str] | None = None,
        proto_schema: str = "",
        input_schema: dict | None = None,
        output_schema: dict | None = None,
    ) -> str:
        """Save all workspace files as a reusable skill with schema metadata. Users can run it with /run <name>."""
        dependencies = dependencies or []

        # Bundle all workspace files into JSON
        bundle: dict[str, str] = {}
        for root, _dirs, files in os.walk(workspace_path):
            for fname in files:
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, workspace_path)
                try:
                    with open(full) as f:
                        bundle[rel] = f.read()
                except Exception:
                    pass

        if not bundle:
            return "Error: workspace is empty, nothing to save."

        code_json = json.dumps(bundle, ensure_ascii=False)

        skill = await skill_repo.create(
            SkillCreate(
                name=name,
                description=description,
                code=code_json,
                entry_point=entry_point,
                dependencies=dependencies,
                proto_schema=proto_schema or None,
                input_schema=input_schema or None,
                output_schema=output_schema or None,
            ),
            user_id=user_id,
        )
        return f"Skill '{name}' saved (id={skill.id}). Run with: /run {name}"

    return save_skill
