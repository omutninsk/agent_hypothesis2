from __future__ import annotations

from uuid import UUID

import asyncpg

from src.db.models import Task, TaskCreate, TaskStatus


class TasksRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(self, task: TaskCreate) -> Task:
        row = await self._pool.fetchrow(
            """
            INSERT INTO tasks (user_id, chat_id, description, max_iterations)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            task.user_id,
            task.chat_id,
            task.description,
            task.max_iterations,
        )
        return Task(**dict(row))

    async def update_status(
        self, task_id: UUID, status: TaskStatus, result: str | None = None
    ) -> None:
        await self._pool.execute(
            """
            UPDATE tasks SET status = $1, result = $2, updated_at = NOW()
            WHERE id = $3
            """,
            status.value,
            result,
            task_id,
        )

    async def set_skill_id(self, task_id: UUID, skill_id: int) -> None:
        await self._pool.execute(
            "UPDATE tasks SET skill_id = $1, updated_at = NOW() WHERE id = $2",
            skill_id,
            task_id,
        )

    async def increment_iteration(self, task_id: UUID) -> int:
        row = await self._pool.fetchrow(
            """
            UPDATE tasks SET iteration = iteration + 1, updated_at = NOW()
            WHERE id = $1
            RETURNING iteration
            """,
            task_id,
        )
        return row["iteration"]

    async def get_active_by_user(self, user_id: int) -> list[Task]:
        rows = await self._pool.fetch(
            """
            SELECT * FROM tasks
            WHERE user_id = $1 AND status IN ('pending', 'running')
            ORDER BY created_at DESC
            """,
            user_id,
        )
        return [Task(**dict(r)) for r in rows]

    async def get_by_id(self, task_id: UUID) -> Task | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM tasks WHERE id = $1", task_id
        )
        return Task(**dict(row)) if row else None
