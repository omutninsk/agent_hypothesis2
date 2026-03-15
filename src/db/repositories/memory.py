from __future__ import annotations

import asyncpg

from src.db.models import MemoryEntry


class MemoryRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def save(self, key: str, content: str, user_id: int) -> MemoryEntry:
        row = await self._pool.fetchrow(
            """
            INSERT INTO agent_memory (key, content, created_by)
            VALUES ($1, $2, $3)
            ON CONFLICT (key, created_by)
            DO UPDATE SET content = $2, updated_at = NOW()
            RETURNING *
            """,
            key,
            content,
            user_id,
        )
        return MemoryEntry(**dict(row))

    async def recall(self, key: str, user_id: int) -> MemoryEntry | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM agent_memory WHERE key = $1 AND created_by = $2",
            key,
            user_id,
        )
        return MemoryEntry(**dict(row)) if row else None

    async def recall_all(self, user_id: int) -> list[MemoryEntry]:
        rows = await self._pool.fetch(
            "SELECT * FROM agent_memory WHERE created_by = $1 ORDER BY updated_at DESC",
            user_id,
        )
        return [MemoryEntry(**dict(r)) for r in rows]

    async def search(self, query: str, user_id: int) -> list[MemoryEntry]:
        pattern = f"%{query}%"
        rows = await self._pool.fetch(
            """
            SELECT * FROM agent_memory
            WHERE created_by = $1
              AND (key ILIKE $2 OR content ILIKE $2)
            ORDER BY updated_at DESC
            LIMIT 10
            """,
            user_id,
            pattern,
        )
        return [MemoryEntry(**dict(r)) for r in rows]

    async def recall_by_prefix(self, prefix: str, user_id: int) -> list[MemoryEntry]:
        rows = await self._pool.fetch(
            "SELECT * FROM agent_memory WHERE created_by = $1 AND key LIKE $2 ORDER BY updated_at DESC",
            user_id,
            f"{prefix}%",
        )
        return [MemoryEntry(**dict(r)) for r in rows]

    async def delete_by_prefix(self, prefix: str, user_id: int) -> int:
        result = await self._pool.execute(
            "DELETE FROM agent_memory WHERE created_by = $1 AND key LIKE $2",
            user_id,
            f"{prefix}%",
        )
        return int(result.split()[-1])

    async def delete(self, key: str, user_id: int) -> bool:
        result = await self._pool.execute(
            "DELETE FROM agent_memory WHERE key = $1 AND created_by = $2",
            key,
            user_id,
        )
        return result == "DELETE 1"
