from __future__ import annotations

from typing import TYPE_CHECKING

from src.agent.prompts import en, ru

if TYPE_CHECKING:
    from src.db.repositories.memory import MemoryRepository

_LANGS = {"en": en, "ru": ru}

EDITABLE_PROMPTS = [
    "REACT_SYSTEM",
    "CODER_SYSTEM",
    "SUPERVISOR_SYSTEM",
    "CODE_REVIEWER_SYSTEM",
    "FILE_ANALYZER_SYSTEM",
    "PERSISTENT_PLANNING_ADDON",
    "CODER_PLANNING_ADDON",
    "SCHEDULING_ADDON",
]


def get_prompts(lang: str = "en"):
    """Return the prompt module for the given language code."""
    return _LANGS.get(lang, en)


async def get_prompt_text(
    name: str, lang: str, memory_repo: MemoryRepository | None = None
) -> str:
    """Get prompt text, checking for runtime override in memory first."""
    if memory_repo:
        override = await memory_repo.recall(f"_prompt:{name}", user_id=0)
        if override:
            return override.content
    module = _LANGS.get(lang, en)
    return getattr(module, name, "")


def format_tool_descriptions(tools: list) -> str:
    lines = []
    for t in tools:
        desc = t.description or ""
        if hasattr(t, "args_schema") and t.args_schema:
            schema = t.args_schema.model_json_schema()
            props = schema.get("properties", {})
            args_desc = ", ".join(
                f'{k}: {v.get("description", v.get("type", ""))}'
                for k, v in props.items()
            )
            lines.append(f"- {t.name}({args_desc}): {desc}")
        else:
            lines.append(f"- {t.name}: {desc}")
    return "\n".join(lines)


# Backward compatibility — default English exports
from src.agent.prompts.en import *  # noqa: F401,F403,E402
