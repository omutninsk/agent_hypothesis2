from __future__ import annotations

from src.agent.core import ReactAgent, build_llm
from src.agent.prompts import SUPERVISOR_SYSTEM
from src.agent.tools.search_skills import make_search_skills_tool
from src.agent.tools.run_existing_skill import make_run_existing_skill_tool
from src.agent.tools.delegate_to_coder import make_delegate_to_coder_tool
from src.config import Settings
from src.db.repositories.skills import SkillsRepository
from src.sandbox.manager import SandboxManager


def build_supervisor_agent(
    settings: Settings,
    sandbox: SandboxManager,
    skill_repo: SkillsRepository,
    user_id: int,
) -> ReactAgent:
    llm = build_llm(settings)

    tools = [
        make_search_skills_tool(skill_repo),
        make_run_existing_skill_tool(skill_repo, sandbox),
        make_delegate_to_coder_tool(settings, sandbox, skill_repo, user_id),
    ]

    return ReactAgent(
        llm=llm,
        tools=tools,
        max_iterations=6,
        system_prompt=SUPERVISOR_SYSTEM,
    )
