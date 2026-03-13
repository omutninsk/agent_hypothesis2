from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message


class AuthMiddleware(BaseMiddleware):
    def __init__(self, allowed_user_ids: list[int]) -> None:
        self.allowed = set(allowed_user_ids) if allowed_user_ids else None

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        if self.allowed and event.from_user and event.from_user.id not in self.allowed:
            await event.reply("Access denied.")
            return None
        return await handler(event, data)
