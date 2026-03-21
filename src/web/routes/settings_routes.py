from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

# Whitelist of safe env fields (no secrets)
_SAFE_ENV_FIELDS = {
    "llm_base_url",
    "llm_model",
    "llm_context_size",
    "llm_temperature",
    "llm_max_tokens",
    "agent_max_iterations",
    "feature_persistent_planning",
    "feature_inject_datetime",
    "prompt_language",
    "log_level",
    "docker_sandbox_image",
    "docker_execution_timeout",
    "docker_memory_limit",
    "docker_cpu_quota",
    "docker_network_disabled",
    "web_host",
    "web_port",
    "web_enabled",
    "planning_decomposition_depth",
    "planning_min_steps",
    "planning_max_steps",
}


class AgentSettingUpdate(BaseModel):
    key: str
    value: str


class EnvSettingUpdate(BaseModel):
    field: str
    value: str


# --- Agent Settings (_setting:* in memory) ---

@router.get("/agent")
async def list_agent_settings(request: Request) -> dict:
    memory_repo = request.app.state.memory_repo
    entries = await memory_repo.recall_by_prefix("_setting:", request.app.state.web_user_id)
    return {
        "settings": [
            {"key": e.key.removeprefix("_setting:"), "value": e.content}
            for e in entries
        ]
    }


@router.put("/agent")
async def set_agent_setting(body: AgentSettingUpdate, request: Request) -> dict:
    memory_repo = request.app.state.memory_repo
    await memory_repo.save(f"_setting:{body.key}", body.value, request.app.state.web_user_id)
    return {"status": "saved", "key": body.key}


@router.delete("/agent/{key}")
async def delete_agent_setting(key: str, request: Request) -> dict:
    memory_repo = request.app.state.memory_repo
    deleted = await memory_repo.delete(f"_setting:{key}", request.app.state.web_user_id)
    return {"status": "deleted" if deleted else "not_found", "key": key}


# --- Env Settings (Settings object + .env file) ---

@router.get("/env")
async def list_env_settings(request: Request) -> dict:
    settings = request.app.state.settings
    result = {}
    for field in _SAFE_ENV_FIELDS:
        if hasattr(settings, field):
            val = getattr(settings, field)
            if isinstance(val, list):
                result[field] = ",".join(str(v) for v in val)
            else:
                result[field] = str(val)
    return {"settings": result}


@router.put("/env")
async def update_env_setting(body: EnvSettingUpdate, request: Request) -> dict:
    if body.field not in _SAFE_ENV_FIELDS:
        return {"error": f"Field '{body.field}' is not editable"}

    settings = request.app.state.settings
    if not hasattr(settings, body.field):
        return {"error": f"Unknown field: {body.field}"}

    # Coerce value to the correct type
    current = getattr(settings, body.field)
    try:
        if isinstance(current, bool):
            coerced = body.value.lower() in ("true", "1", "yes")
        elif isinstance(current, int):
            coerced = int(body.value)
        elif isinstance(current, float):
            coerced = float(body.value)
        else:
            coerced = body.value
    except (ValueError, TypeError) as e:
        return {"error": f"Invalid value: {e}"}

    # Hot-reload in runtime
    object.__setattr__(settings, body.field, coerced)

    # Persist to .env file
    _update_env_file(body.field.upper(), body.value)

    return {"status": "updated", "field": body.field, "value": str(coerced)}


def _update_env_file(key: str, value: str) -> None:
    """Update or add a key=value pair in the .env file."""
    env_path = ".env"
    try:
        with open(env_path, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []

    pattern = re.compile(rf"^{re.escape(key)}\s*=", re.IGNORECASE)
    found = False
    new_lines = []
    for line in lines:
        if pattern.match(line):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"{key}={value}\n")

    with open(env_path, "w") as f:
        f.writelines(new_lines)
