from __future__ import annotations

from src.agent.core import ReactAgent, build_llm
from src.agent.prompts import SUPERVISOR_SYSTEM
from src.agent.tools.search_skills import make_search_skills_tool
from src.agent.tools.run_existing_skill import make_run_existing_skill_tool
from src.agent.tools.delegate_to_coder import make_delegate_to_coder_tool
from src.agent.tools.save_memory import make_save_memory_tool
from src.agent.tools.recall_memory import make_recall_memory_tool
from src.agent.tools.web_search import make_web_search_tool
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
) -> ReactAgent:
    llm = build_llm(settings)

    tools = [
        make_recall_memory_tool(memory_repo, user_id),
        make_save_memory_tool(memory_repo, user_id),
        make_update_context_tool(memory_repo, user_id),
        make_search_knowledge_tool(knowledge_repo, user_id),
        make_save_knowledge_tool(knowledge_repo, user_id),
        make_web_search_tool(),
        make_search_skills_tool(skill_repo),
        make_run_existing_skill_tool(skill_repo, sandbox),
        make_delete_skill_tool(skill_repo, settings.skills_dir),
        make_delegate_to_coder_tool(settings, sandbox, skill_repo, user_id),
    ]

    return ReactAgent(
        llm=llm,
        tools=tools,
        max_iterations=15,
        system_prompt=SUPERVISOR_SYSTEM,
    )
