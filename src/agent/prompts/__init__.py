from __future__ import annotations

from src.agent.prompts import en, ru

_LANGS = {"en": en, "ru": ru}


def get_prompts(lang: str = "en"):
    """Return the prompt module for the given language code."""
    return _LANGS.get(lang, en)


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
