from __future__ import annotations

import re

import asyncpg

from src.db.models import MemoryEntry


def _build_or_query(text: str, max_terms: int = 8) -> str:
    """Extract keywords from *text* and join with OR for tsquery.

    - Splits on non-word characters
    - Drops words shorter than 3 chars (catches most stop words cheaply)
    - Deduplicates and takes up to *max_terms*
    - Returns a string like ``"word1 OR word2 OR word3"``
    """
    words = re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]+", text)
    seen: set[str] = set()
    keywords: list[str] = []
    for w in words:
        low = w.lower()
        if len(low) < 3 or low in seen:
            continue
        seen.add(low)
        keywords.append(low)
        if len(keywords) >= max_terms:
            break
    return " OR ".join(keywords) if keywords else text


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

    async def search_by_prefix_fts(
        self, prefix: str, query: str, user_id: int, limit: int = 10
    ) -> list[MemoryEntry]:
        """FTS search within entries matching a key prefix.

        Uses OR-based keyword matching with Russian stemming config.
        Falls back to ILIKE on the longest keyword if FTS returns nothing.
        """
        or_query = _build_or_query(query)
        rows = await self._pool.fetch(
            """
            SELECT id, key, content, created_by, created_at, updated_at,
                   ts_rank(search_vector, websearch_to_tsquery('russian', $1)) AS rank
            FROM agent_memory
            WHERE created_by = $2
              AND key LIKE $3
              AND search_vector @@ websearch_to_tsquery('russian', $1)
            ORDER BY rank DESC
            LIMIT $4
            """,
            or_query, user_id, f"{prefix}%", limit,
        )
        if rows:
            return [MemoryEntry(**{k: v for k, v in dict(r).items() if k != "rank"}) for r in rows]

        # Fallback: ILIKE on the longest keyword (not full query)
        keywords = re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]+", query)
        longest = max(keywords, key=len) if keywords else query
        pattern = f"%{longest}%"
        rows = await self._pool.fetch(
            """
            SELECT * FROM agent_memory
            WHERE created_by = $1
              AND key LIKE $2
              AND (key ILIKE $3 OR content ILIKE $3)
            ORDER BY updated_at DESC
            LIMIT $4
            """,
            user_id, f"{prefix}%", pattern, limit,
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
