from __future__ import annotations

import json
from functools import cached_property

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings


def _parse_prompt_blocks(raw: str) -> list[str]:
    raw = raw.strip()
    if not raw:
        return []
    return [s.strip().lower() for s in raw.split(",") if s.strip()]


class Settings(BaseSettings):
    # LLM
    llm_base_url: str = "https://aisupervisor.ru/v1"
    llm_api_key: SecretStr = Field(alias="LLM_API_KEY")
    llm_model: str = "qwen3_4b_instruct"
    llm_context_size: int = 32768
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096

    # Telegram
    telegram_bot_token: SecretStr = Field(alias="TELEGRAM_BOT_TOKEN")
    telegram_allowed_user_ids: list[int] = []

    # PostgreSQL
    postgres_dsn: str = "postgresql://agent:agent@localhost:5432/agent_db"

    # Docker
    docker_sandbox_image: str = "agent-sandbox:latest"
    docker_execution_timeout: int = 60
    docker_memory_limit: str = "512m"
    docker_cpu_quota: int = 50000
    docker_network_disabled: bool = False

    # Agent
    agent_max_iterations: int = 200
    skills_dir: str = "/app/skills"

    # Web UI
    web_host: str = "0.0.0.0"
    web_port: int = 8080
    web_enabled: bool = True

    # Agent features
    feature_persistent_planning: bool = True
    feature_inject_datetime: bool = False
    prompt_language: str = "ru"

    # Logging
    log_level: str = "INFO"
    # Stored as str to avoid pydantic-settings v3 JSON-parsing list fields
    log_prompt_blocks_raw: str = Field("", alias="LOG_PROMPT_BLOCKS")

    @property
    def log_prompt_blocks(self) -> list[str]:
        return _parse_prompt_blocks(self.log_prompt_blocks_raw)

    @log_prompt_blocks.setter
    def log_prompt_blocks(self, value: list[str]) -> None:
        object.__setattr__(self, "log_prompt_blocks_raw", ",".join(value))

    @field_validator("telegram_allowed_user_ids", mode="before")
    @classmethod
    def parse_user_ids(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "populate_by_name": True,
    }
