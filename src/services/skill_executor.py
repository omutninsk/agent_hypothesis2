from __future__ import annotations

import json
import os
import shutil
import tempfile

from src.config import Settings
from src.db.models import ExecutionResult, Skill
from src.db.repositories.skills import SkillsRepository
from src.sandbox.manager import SandboxManager
from src.sandbox.workspace import WorkspaceManager


class SkillExecutor:
    def __init__(
        self,
        sandbox_manager: SandboxManager,
        workspace_manager: WorkspaceManager,
        skill_repo: SkillsRepository,
        settings: Settings,
    ) -> None:
        self.sandbox = sandbox_manager
        self.workspaces = workspace_manager
        self.skill_repo = skill_repo
        self.settings = settings

    async def execute(self, skill: Skill, args: str = "") -> ExecutionResult:
        tmpdir = tempfile.mkdtemp(prefix="skill_run_")
        try:
            # Unpack skill files
            bundle = json.loads(skill.code)
            for filename, content in bundle.items():
                safe = os.path.normpath(filename)
                if safe.startswith("..") or safe.startswith("/"):
                    continue
                full = os.path.join(tmpdir, safe)
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, "w") as f:
                    f.write(content)

            # Install dependencies
            if skill.dependencies:
                deps = " ".join(skill.dependencies)
                await self.sandbox.execute(
                    command=f"pip install {deps}",
                    workspace_path=tmpdir,
                    timeout=60,
                )

            # Run
            cmd = f"python /workspace/{skill.entry_point}"
            if args:
                cmd += f" {args}"

            return await self.sandbox.execute(
                command=cmd,
                workspace_path=tmpdir,
                timeout=self.settings.docker_execution_timeout,
            )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    async def execute_by_name(
        self, name: str, args: str = ""
    ) -> ExecutionResult | None:
        skill = await self.skill_repo.get_by_name(name)
        if not skill:
            return None
        return await self.execute(skill, args)
