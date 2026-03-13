from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


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


# --- Execution ---

class ExecutionResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    duration_seconds: float = 0.0
