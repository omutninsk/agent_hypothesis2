from __future__ import annotations

import asyncpg

from src.db.models import ScheduledTask, ScheduledTaskCreate


class ScheduledTasksRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(self, st: ScheduledTaskCreate) -> ScheduledTask:
        row = await self._pool.fetchrow(
            """
            INSERT INTO scheduled_tasks
                (user_id, chat_id, description, interval_minutes, next_run_at, is_active)
            VALUES ($1, $2, $3, $4, NOW() + make_interval(mins => $5), false)
            RETURNING *
            """,
            st.user_id,
            st.chat_id,
            st.description,
            st.interval_minutes,
            float(st.delay_minutes),
        )
        return ScheduledTask(**dict(row))

    async def get_due(self) -> list[ScheduledTask]:
        rows = await self._pool.fetch(
            """
            SELECT * FROM scheduled_tasks
            WHERE is_active = true AND next_run_at <= NOW()
            ORDER BY next_run_at
            """,
        )
        return [ScheduledTask(**dict(r)) for r in rows]

    async def mark_running(self, st_id: int) -> None:
        """Advance next_run_at for recurring or deactivate for one-shot."""
        await self._pool.execute(
            """
            UPDATE scheduled_tasks SET
                run_count = run_count + 1,
                last_run_at = NOW(),
                next_run_at = CASE
                    WHEN interval_minutes IS NOT NULL
                    THEN NOW() + make_interval(mins => interval_minutes)
                    ELSE next_run_at
                END,
                is_active = CASE
                    WHEN interval_minutes IS NOT NULL THEN true
                    ELSE false
                END,
                updated_at = NOW()
            WHERE id = $1
            """,
            st_id,
        )

    async def set_last_result(self, st_id: int, result: str) -> None:
        await self._pool.execute(
            """
            UPDATE scheduled_tasks SET last_result = $1, updated_at = NOW()
            WHERE id = $2
            """,
            result[:2000],
            st_id,
        )

    async def list_by_user(
        self, user_id: int, active_only: bool = True
    ) -> list[ScheduledTask]:
        if active_only:
            rows = await self._pool.fetch(
                """
                SELECT * FROM scheduled_tasks
                WHERE user_id = $1 AND is_active = true
                ORDER BY next_run_at
                """,
                user_id,
            )
        else:
            rows = await self._pool.fetch(
                """
                SELECT * FROM scheduled_tasks
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT 50
                """,
                user_id,
            )
        return [ScheduledTask(**dict(r)) for r in rows]

    async def confirm(self, st_id: int, user_id: int) -> bool:
        """Activate a pending (is_active=false, run_count=0) scheduled task."""
        result = await self._pool.execute(
            """
            UPDATE scheduled_tasks
            SET is_active = true, next_run_at = NOW() + make_interval(mins => COALESCE(interval_minutes, 0)), updated_at = NOW()
            WHERE id = $1 AND user_id = $2 AND is_active = false AND run_count = 0
            """,
            st_id,
            user_id,
        )
        return result.split()[-1] != "0"

    async def list_pending(self, user_id: int) -> list[ScheduledTask]:
        """List tasks awaiting user confirmation."""
        rows = await self._pool.fetch(
            """
            SELECT * FROM scheduled_tasks
            WHERE user_id = $1 AND is_active = false AND run_count = 0
            ORDER BY created_at DESC
            """,
            user_id,
        )
        return [ScheduledTask(**dict(r)) for r in rows]

    async def cancel(self, st_id: int, user_id: int) -> bool:
        result = await self._pool.execute(
            """
            UPDATE scheduled_tasks SET is_active = false, updated_at = NOW()
            WHERE id = $1 AND user_id = $2 AND is_active = true
            """,
            st_id,
            user_id,
        )
        return result.split()[-1] != "0"

    async def count_active(self, user_id: int) -> int:
        row = await self._pool.fetchrow(
            "SELECT COUNT(*) AS cnt FROM scheduled_tasks WHERE user_id = $1 AND is_active = true",
            user_id,
        )
        return row["cnt"]
