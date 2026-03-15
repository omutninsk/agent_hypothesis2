from __future__ import annotations

import json
import logging
import re

from src.agent.core import build_llm
from src.config import Settings
from src.db.repositories.memory import MemoryRepository

logger = logging.getLogger(__name__)

_REFLECTION_PROMPT = """Task: {task}
Result: {result}

Extract 0-3 reusable insights from this task. An insight is something useful for future tasks: a working API, a scraping technique, a user preference, a gotcha to avoid.

Respond ONLY with a JSON array. Each item: {{"key": "short_topic", "content": "what you learned"}}
If nothing useful, respond with: []"""

_MAX_INSIGHTS = 3


def _parse_json_array(text: str) -> list[dict]:
    """Extract a JSON array from LLM response, handling markdown code blocks."""
    text = text.strip()
    # Strip markdown code block wrappers
    m = re.search(r"```(?:json)?\s*(\[.*?])\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    else:
        # Try to find a bare JSON array
        m = re.search(r"\[.*]", text, re.DOTALL)
        if m:
            text = m.group(0)
    return json.loads(text)


async def reflect_and_save(
    settings: Settings,
    memory_repo: MemoryRepository,
    user_id: int,
    task_description: str,
    task_result: str,
) -> list[dict]:
    """Run a single LLM call to extract insights and save them.

    Returns list of saved insights (may be empty).
    Never raises — all errors are caught and logged.
    """
    try:
        prompt = _REFLECTION_PROMPT.format(
            task=task_description[:1000],
            result=task_result[:1500],
        )

        llm = build_llm(settings)
        response = await llm.ainvoke(prompt)
        raw = response.content if isinstance(response.content, str) else str(response.content)
        logger.info("Reflection response: %.500s", raw)

        items = _parse_json_array(raw)
        if not isinstance(items, list):
            return []

        saved: list[dict] = []
        for item in items[:_MAX_INSIGHTS]:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key", "")).strip()
            content = str(item.get("content", "")).strip()
            if not key or not content:
                continue
            await memory_repo.save(
                key=f"_insight:{key}",
                content=content,
                user_id=user_id,
            )
            saved.append({"key": key, "content": content})
            logger.info("Saved insight: %s = %s", key, content[:100])

        return saved

    except Exception:
        logger.exception("Reflection failed (non-fatal)")
        return []
