from __future__ import annotations

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from src.agent.prompts import SYSTEM_PROMPT
from src.agent.tools.write_file import make_write_file_tool
from src.agent.tools.read_file import make_read_file_tool
from src.agent.tools.execute_code import make_execute_code_tool
from src.agent.tools.save_skill import make_save_skill_tool
from src.agent.tools.list_skills import make_list_skills_tool
from src.agent.tools.run_skill import make_run_skill_tool
from src.config import Settings
from src.db.repositories.skills import SkillsRepository
from src.sandbox.manager import SandboxManager


def build_llm(settings: Settings) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key.get_secret_value(),
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )


def build_agent(
    settings: Settings,
    sandbox: SandboxManager,
    skill_repo: SkillsRepository,
    workspace_path: str,
    user_id: int,
):
    llm = build_llm(settings)

    tools = [
        make_write_file_tool(workspace_path),
        make_read_file_tool(workspace_path),
        make_execute_code_tool(sandbox, workspace_path),
        make_save_skill_tool(skill_repo, workspace_path, user_id),
        make_list_skills_tool(skill_repo),
        make_run_skill_tool(skill_repo, sandbox),
    ]

    return create_react_agent(
        model=llm,
        tools=tools,
        prompt=SYSTEM_PROMPT,
    )
