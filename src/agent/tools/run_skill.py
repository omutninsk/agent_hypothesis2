from __future__ import annotations

import json
import os
import tempfile

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.db.repositories.skills import SkillsRepository
from src.sandbox.manager import SandboxManager


class RunSkillInput(BaseModel):
    name: str = Field(description="Name of the skill to run")
    args: str = Field(default="", description="Command-line arguments to pass")


def make_run_skill_tool(skill_repo: SkillsRepository, sandbox: SandboxManager):
    @tool(args_schema=RunSkillInput)
    async def run_skill(name: str, args: str = "") -> str:
        """Run a previously saved skill by name."""
        skill = await skill_repo.get_by_name(name)
        if not skill:
            return f"Error: skill '{name}' not found."

        # Unpack skill files into temp workspace
        tmpdir = tempfile.mkdtemp(prefix="skill_")
        try:
            bundle = json.loads(skill.code)
            for filename, content in bundle.items():
                safe = os.path.normpath(filename)
                if safe.startswith("..") or safe.startswith("/"):
                    continue
                full = os.path.join(tmpdir, safe)
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, "w") as f:
                    f.write(content)

            # Install dependencies if any
            if skill.dependencies:
                deps = " ".join(skill.dependencies)
                await sandbox.execute(
                    command=f"pip install {deps}",
                    workspace_path=tmpdir,
                    timeout=60,
                )

            # Run the skill
            cmd = f"python /workspace/{skill.entry_point}"
            if args:
                cmd += f" {args}"

            result = await sandbox.execute(
                command=cmd, workspace_path=tmpdir, timeout=60
            )

            parts = []
            if result.stdout:
                parts.append(result.stdout[:5000])
            if result.stderr:
                parts.append(f"STDERR: {result.stderr[:2000]}")
            if result.timed_out:
                parts.append("TIMED OUT")
            parts.append(f"EXIT_CODE: {result.exit_code}")
            return "\n".join(parts)

        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    return run_skill
