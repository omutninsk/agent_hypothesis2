from __future__ import annotations

import asyncpg

from src.db.models import Skill, SkillCreate


class SkillsRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(self, skill: SkillCreate, user_id: int) -> Skill:
        row = await self._pool.fetchrow(
            """
            INSERT INTO skills (name, description, code, language, entry_point, dependencies, tags, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
            """,
            skill.name,
            skill.description,
            skill.code,
            skill.language,
            skill.entry_point,
            skill.dependencies,
            skill.tags,
            user_id,
        )
        return Skill(**dict(row))

    async def get_by_name(self, name: str) -> Skill | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM skills WHERE name = $1", name
        )
        return Skill(**dict(row)) if row else None

    async def get_by_id(self, skill_id: int) -> Skill | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM skills WHERE id = $1", skill_id
        )
        return Skill(**dict(row)) if row else None

    async def list_all(self) -> list[Skill]:
        rows = await self._pool.fetch(
            "SELECT * FROM skills ORDER BY created_at DESC"
        )
        return [Skill(**dict(r)) for r in rows]

    async def delete(self, skill_id: int) -> bool:
        result = await self._pool.execute(
            "DELETE FROM skills WHERE id = $1", skill_id
        )
        return result == "DELETE 1"

    async def update_code(self, skill_id: int, code: str) -> None:
        await self._pool.execute(
            "UPDATE skills SET code = $1, updated_at = NOW() WHERE id = $2",
            code,
            skill_id,
        )
