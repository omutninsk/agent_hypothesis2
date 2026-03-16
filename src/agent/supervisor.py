from __future__ import annotations

from src.agent.core import ReactAgent, build_llm
from src.agent.prompts import SUPERVISOR_SYSTEM
from src.agent.tools.search_skills import make_search_skills_tool
from src.agent.tools.run_existing_skill import make_run_existing_skill_tool
from src.agent.tools.delegate_to_coder import make_delegate_to_coder_tool
from src.agent.tools.delegate_to_file_analyzer import make_delegate_to_file_analyzer_tool
from src.agent.tools.save_memory import make_save_memory_tool
from src.agent.tools.recall_memory import make_recall_memory_tool
from src.agent.tools.web_search import make_web_search_tool
from src.agent.tools.fetch_url import make_fetch_url_tool
from src.agent.tools.get_current_datetime import make_get_current_datetime_tool
from src.agent.tools.delete_skill import make_delete_skill_tool
from src.agent.tools.save_knowledge import make_save_knowledge_tool
from src.agent.tools.search_knowledge import make_search_knowledge_tool
from src.agent.tools.update_context import make_update_context_tool
from src.config import Settings
from src.db.repositories.knowledge import KnowledgeRepository
from src.db.repositories.memory import MemoryRepository
from src.db.repositories.skills import SkillsRepository
from src.sandbox.manager import SandboxManager


def build_supervisor_agent(
    settings: Settings,
    sandbox: SandboxManager,
    skill_repo: SkillsRepository,
    memory_repo: MemoryRepository,
    knowledge_repo: KnowledgeRepository,
    user_id: int,
    extra_tools: list | None = None,
    system_prompt_addon: str = "",
) -> ReactAgent:
    llm = build_llm(settings)

    tools = [
        make_recall_memory_tool(memory_repo, user_id),
        make_save_memory_tool(memory_repo, user_id),
        make_update_context_tool(memory_repo, user_id),
        make_search_knowledge_tool(knowledge_repo, user_id),
        make_save_knowledge_tool(knowledge_repo, user_id),
        make_web_search_tool(sandbox),
        make_fetch_url_tool(sandbox),
        make_get_current_datetime_tool(),
        make_search_skills_tool(skill_repo),
        make_run_existing_skill_tool(skill_repo, sandbox),
        make_delete_skill_tool(skill_repo, settings.skills_dir),
        make_delegate_to_coder_tool(settings, sandbox, skill_repo, user_id),
        make_delegate_to_file_analyzer_tool(settings, sandbox),
    ]

    if extra_tools:
        tools.extend(extra_tools)

    system_prompt = SUPERVISOR_SYSTEM
    if system_prompt_addon:
        system_prompt = system_prompt.replace(
            "\nRules:\n", f"\n{system_prompt_addon}\nRules:\n", 1
        )

    required_tools_any = {
        "web_search",
        "fetch_url",
        "delegate_to_coder",
        "run_existing_skill",
        "search_knowledge",
        "delegate_to_file_analyzer",
    }
    if extra_tools:
        for t in extra_tools:
            required_tools_any.add(t.name)

    # Plan enforcement: if show_plan tool is present, block action tools until plan shown
    plan_tool_name = None
    action_tools: set[str] = set()
    if extra_tools:
        for t in extra_tools:
            if t.name == "show_plan":
                plan_tool_name = "show_plan"
                action_tools = {
                    "delegate_to_coder",
                    "run_existing_skill",
                    "delete_skill",
                    "delegate_to_file_analyzer",
                }
                break

    return ReactAgent(
        llm=llm,
        tools=tools,
        max_iterations=200,
        system_prompt=system_prompt,
        required_tools_any=required_tools_any,
        settings=settings,
        required_plan_tool=plan_tool_name,
        action_tool_names=action_tools,
        min_plans_before_failure=2,
    )
