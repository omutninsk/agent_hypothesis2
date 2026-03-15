from __future__ import annotations

import json
import os
import shutil
import tempfile

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.db.repositories.skills import SkillsRepository
from src.sandbox.manager import SandboxManager


class RunExistingSkillInput(BaseModel):
    name: str = Field(description="Name of the skill to run")
    input_json: str = Field(
        default="{}",
        description='JSON string to pass as stdin, e.g. \'{"url": "https://example.com"}\'',
    )


def make_run_existing_skill_tool(
    skill_repo: SkillsRepository, sandbox: SandboxManager
):
    @tool(args_schema=RunExistingSkillInput)
    async def run_existing_skill(name: str, input_json: str = "{}") -> str:
        """Run a saved skill by name, passing JSON input via stdin. Returns the skill's output."""
        skill = await skill_repo.get_by_name(name)
        if not skill:
            return f"Error: skill '{name}' not found."

        try:
            json.loads(input_json)
        except json.JSONDecodeError:
            return f"Error: input_json is not valid JSON: {input_json[:200]}"

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

            if skill.dependencies:
                deps = " ".join(skill.dependencies)
                await sandbox.execute(
                    command=f"pip install {deps}",
                    workspace_path=tmpdir,
                    timeout=60,
                )

            escaped = input_json.replace("'", "'\\''")
            cmd = f"echo '{escaped}' | python /workspace/{skill.entry_point}"

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
            shutil.rmtree(tmpdir, ignore_errors=True)

    return run_existing_skill
