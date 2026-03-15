from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# --- Skill ---

class SkillCreate(BaseModel):
    name: str = Field(..., max_length=128, pattern=r"^[a-z][a-z0-9_]*$")
    description: str
    code: str  # JSON: {"filename": "content", ...}
    language: str = "python"
    entry_point: str = "main.py"
    dependencies: list[str] = []
    tags: list[str] = []
    proto_schema: Optional[str] = None
    input_schema: Optional[dict] = None
    output_schema: Optional[dict] = None


class Skill(BaseModel):
    id: int
    name: str
    description: str
    code: str
    language: str
    entry_point: str
    dependencies: list[str]
    tags: list[str]
    created_by: int
    created_at: datetime
    updated_at: datetime
    proto_schema: Optional[str] = None
    input_schema: Optional[dict] = None
    output_schema: Optional[dict] = None

    @field_validator("input_schema", "output_schema", mode="before")
    @classmethod
    def _parse_json_str(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v


# --- Task ---

class TaskCreate(BaseModel):
    user_id: int
    chat_id: int
    description: str
    max_iterations: int = 10


class Task(BaseModel):
    id: UUID
    user_id: int
    chat_id: int
    description: str
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    skill_id: Optional[int] = None
    iteration: int = 0
    max_iterations: int = 10
    created_at: datetime
    updated_at: datetime


# --- Conversation ---

class ConversationMessage(BaseModel):
    task_id: UUID
    role: str
    content: str
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None


# --- Memory ---

class MemoryEntry(BaseModel):
    id: int
    key: str
    content: str
    created_by: int
    created_at: datetime
    updated_at: datetime


# --- Knowledge ---

class KnowledgeEntry(BaseModel):
    id: int
    topic: str
    content: str
    source: Optional[str] = None
    created_by: int
    created_at: datetime


# --- Execution ---

class ExecutionResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    duration_seconds: float = 0.0
