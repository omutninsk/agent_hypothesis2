from __future__ import annotations

import asyncpg


class DatabasePool:
    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    async def connect(self, dsn: str, min_size: int = 2, max_size: int = 10) -> None:
        self._pool = await asyncpg.create_pool(
            dsn, min_size=min_size, max_size=max_size
        )

    async def disconnect(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._pool
