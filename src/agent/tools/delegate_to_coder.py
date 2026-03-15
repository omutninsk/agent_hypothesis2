from __future__ import annotations

import shutil
import tempfile

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.agent.core import build_coder_agent
from src.config import Settings
from src.db.repositories.skills import SkillsRepository
from src.sandbox.manager import SandboxManager


class DelegateToCoderInput(BaseModel):
    task_description: str = Field(
        description="Specific coding task. Include: what the skill does, input/output JSON format, examples. Be concrete."
    )


def make_delegate_to_coder_tool(
    settings: Settings,
    sandbox: SandboxManager,
    skill_repo: SkillsRepository,
    user_id: int,
):
    @tool(args_schema=DelegateToCoderInput)
    async def delegate_to_coder(task_description: str) -> str:
        """Delegate a coding task to the Coder agent. It will write code, test it, and save it as a skill."""
        tmpdir = tempfile.mkdtemp(prefix="coder_ws_")
        try:
            # Snapshot existing skill names before coder runs
            existing = {s.name for s in await skill_repo.list_all()}

            coder = build_coder_agent(
                settings=settings,
                sandbox=sandbox,
                skill_repo=skill_repo,
                workspace_path=tmpdir,
                user_id=user_id,
            )
            result = await coder.ainvoke({"input": task_description})
            coder_output = result.get("output", "Coder agent produced no output.")

            # Detect newly saved skills
            current = {s.name for s in await skill_repo.list_all()}
            new_skills = current - existing
            if new_skills:
                names = ", ".join(sorted(new_skills))
                coder_output += f"\n\nSKILL_SAVED: {names}"
            else:
                coder_output += "\n\nWARNING: No skill was saved by the coder."

            return coder_output
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    return delegate_to_coder
