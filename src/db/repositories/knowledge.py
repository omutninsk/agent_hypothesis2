from __future__ import annotations

import asyncpg

from src.db.models import KnowledgeEntry

_COLUMNS = "id, topic, content, source, created_by, created_at"


class KnowledgeRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def save(
        self, topic: str, content: str, user_id: int, source: str | None = None
    ) -> KnowledgeEntry:
        row = await self._pool.fetchrow(
            f"""
            INSERT INTO knowledge (topic, content, source, created_by)
            VALUES ($1, $2, $3, $4)
            RETURNING {_COLUMNS}
            """,
            topic,
            content,
            source,
            user_id,
        )
        return KnowledgeEntry(**dict(row))

    async def search(
        self, query: str, user_id: int, limit: int = 5
    ) -> list[KnowledgeEntry]:
        # Full-text search with ts_rank
        rows = await self._pool.fetch(
            f"""
            SELECT {_COLUMNS},
                   ts_rank(search_vector, websearch_to_tsquery('simple', $1)) AS rank
            FROM knowledge
            WHERE created_by = $2
              AND search_vector @@ websearch_to_tsquery('simple', $1)
            ORDER BY rank DESC
            LIMIT $3
            """,
            query,
            user_id,
            limit,
        )
        if rows:
            return [KnowledgeEntry(**{k: v for k, v in dict(r).items() if k != "rank"}) for r in rows]

        # Fallback: ILIKE
        pattern = f"%{query}%"
        rows = await self._pool.fetch(
            f"""
            SELECT {_COLUMNS}
            FROM knowledge
            WHERE created_by = $1
              AND (topic ILIKE $2 OR content ILIKE $2)
            ORDER BY created_at DESC
            LIMIT $3
            """,
            user_id,
            pattern,
            limit,
        )
        return [KnowledgeEntry(**dict(r)) for r in rows]

    async def delete(self, entry_id: int, user_id: int) -> bool:
        result = await self._pool.execute(
            "DELETE FROM knowledge WHERE id = $1 AND created_by = $2",
            entry_id,
            user_id,
        )
        return result == "DELETE 1"
