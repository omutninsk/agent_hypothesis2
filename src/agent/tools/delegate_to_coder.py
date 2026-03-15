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
            coder = build_coder_agent(
                settings=settings,
                sandbox=sandbox,
                skill_repo=skill_repo,
                workspace_path=tmpdir,
                user_id=user_id,
            )
            result = await coder.ainvoke({"input": task_description})
            return result.get("output", "Coder agent produced no output.")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    return delegate_to_coder
