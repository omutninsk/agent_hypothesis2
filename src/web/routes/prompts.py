from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.agent.prompts import EDITABLE_PROMPTS, get_prompts

router = APIRouter()
logger = logging.getLogger(__name__)

_PROMPT_USER_ID = 0


class PromptUpdate(BaseModel):
    name: str
    content: str


@router.get("")
async def list_prompts(request: Request) -> dict:
    settings = request.app.state.settings
    memory_repo = request.app.state.memory_repo
    prompts_module = get_prompts(settings.prompt_language)

    result = []
    for name in EDITABLE_PROMPTS:
        original = getattr(prompts_module, name, "")
        override = await memory_repo.recall(f"_prompt:{name}", _PROMPT_USER_ID)
        result.append({
            "name": name,
            "content": override.content if override else original,
            "is_override": override is not None,
            "original_length": len(original),
        })

    return {"prompts": result}


@router.put("")
async def save_prompt_override(body: PromptUpdate, request: Request) -> dict:
    if body.name not in EDITABLE_PROMPTS:
        return {"error": f"Unknown prompt: {body.name}"}

    memory_repo = request.app.state.memory_repo
    await memory_repo.save(f"_prompt:{body.name}", body.content, _PROMPT_USER_ID)
    return {"status": "saved", "name": body.name}


@router.delete("/{name}")
async def reset_prompt(name: str, request: Request) -> dict:
    if name not in EDITABLE_PROMPTS:
        return {"error": f"Unknown prompt: {name}"}

    memory_repo = request.app.state.memory_repo
    deleted = await memory_repo.delete(f"_prompt:{name}", _PROMPT_USER_ID)
    return {"status": "reset" if deleted else "no_override", "name": name}
