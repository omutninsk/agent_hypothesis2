from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.agent.prompt_logger import _ALL_BLOCKS

router = APIRouter()


class PromptBlocksConfig(BaseModel):
    enabled: list[str]


@router.get("/config")
async def get_config(request: Request) -> dict:
    settings = request.app.state.settings
    current = set(settings.log_prompt_blocks)
    return {
        "all_blocks": sorted(_ALL_BLOCKS),
        "enabled": sorted(current) if "all" not in current else sorted(_ALL_BLOCKS),
    }


@router.put("/config")
async def update_config(body: PromptBlocksConfig, request: Request) -> dict:
    settings = request.app.state.settings
    # Validate block names
    valid = [b for b in body.enabled if b in _ALL_BLOCKS or b == "all"]
    settings.log_prompt_blocks = valid
    return {"status": "updated", "enabled": valid}
