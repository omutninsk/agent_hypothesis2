from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.agent.core import build_coder_agent, build_code_reviewer_agent
from src.config import Settings
from src.db.repositories.skills import SkillsRepository
from src.sandbox.manager import SandboxManager

logger = logging.getLogger(__name__)


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

                # --- Code Review Phase ---
                try:
                    for skill_name in sorted(new_skills):
                        skill = await skill_repo.get_by_name(skill_name)
                        if not skill:
                            continue
                        entry_point = skill.entry_point or "main.py"

                        # Unpack skill files into tmpdir for review
                        try:
                            bundle = json.loads(skill.code)
                        except (json.JSONDecodeError, TypeError):
                            continue

                        for fname, content in bundle.items():
                            fpath = os.path.join(tmpdir, os.path.normpath(fname))
                            os.makedirs(os.path.dirname(fpath), exist_ok=True)
                            with open(fpath, "w") as f:
                                f.write(content)

                        reviewer = build_code_reviewer_agent(
                            settings=settings,
                            sandbox=sandbox,
                            workspace_path=tmpdir,
                        )
                        review_result = await reviewer.ainvoke({
                            "input": f"Review /workspace/. Entry point: {entry_point}.",
                        })
                        review_output = review_result.get("output", "")

                        # If reviewer fixed issues, re-bundle and update DB
                        if "ISSUES_FIXED" in review_output and "ISSUES_FIXED: 0" not in review_output:
                            new_bundle = {}
                            for fname in bundle:
                                fpath = os.path.join(tmpdir, os.path.normpath(fname))
                                if os.path.exists(fpath):
                                    with open(fpath) as f:
                                        new_bundle[fname] = f.read()
                                else:
                                    new_bundle[fname] = bundle[fname]
                            await skill_repo.update_code(skill.id, json.dumps(new_bundle))

                        coder_output += f"\n\nCODE_REVIEW ({skill_name}): {review_output}"
                except Exception:
                    logger.exception("Code review phase failed (non-blocking)")
            else:
                coder_output += "\n\nWARNING: No skill was saved by the coder."

            return coder_output
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    return delegate_to_coder
