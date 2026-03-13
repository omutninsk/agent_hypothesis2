from __future__ import annotations

from uuid import UUID

import asyncpg

from src.db.models import ConversationMessage


class ConversationsRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, msg: ConversationMessage) -> None:
        await self._pool.execute(
            """
            INSERT INTO conversation_history (task_id, role, content, tool_name, tool_call_id)
            VALUES ($1, $2, $3, $4, $5)
            """,
            msg.task_id,
            msg.role,
            msg.content,
            msg.tool_name,
            msg.tool_call_id,
        )

    async def get_by_task(self, task_id: UUID) -> list[dict]:
        rows = await self._pool.fetch(
            """
            SELECT role, content, tool_name, tool_call_id
            FROM conversation_history
            WHERE task_id = $1
            ORDER BY created_at ASC
            """,
            task_id,
        )
        return [dict(r) for r in rows]

    async def delete_by_task(self, task_id: UUID) -> None:
        await self._pool.execute(
            "DELETE FROM conversation_history WHERE task_id = $1",
            task_id,
        )
