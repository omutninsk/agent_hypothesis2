from __future__ import annotations

import json
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM
    llm_base_url: str = "https://aisupervisor.ru/v1"
    llm_api_key: SecretStr = Field(alias="LLM_API_KEY")
    llm_model: str = "qwen3_4b_instruct"
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

    # Agent features
    feature_persistent_planning: bool = True
    feature_inject_datetime: bool = False
    prompt_language: str = "ru"

    # Logging
    log_level: str = "INFO"

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
