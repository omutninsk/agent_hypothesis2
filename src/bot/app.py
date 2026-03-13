from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from src.bot.handlers import code, skills, start, status
from src.bot.middlewares import AuthMiddleware
from src.config import Settings


def create_bot(settings: Settings) -> tuple[Bot, Dispatcher]:
    bot = Bot(
        token=settings.telegram_bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Auth middleware
    dp.message.middleware(AuthMiddleware(settings.telegram_allowed_user_ids))

    # Register routers
    dp.include_router(start.router)
    dp.include_router(code.router)
    dp.include_router(skills.router)
    dp.include_router(status.router)

    return bot, dp
