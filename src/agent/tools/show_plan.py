from __future__ import annotations

import logging

from aiogram import Bot
from langchain_core.tools import tool
from pydantic import BaseModel, Field, field_validator

from src.bot.formatters import escape, split_message

logger = logging.getLogger(__name__)


class ShowPlanInput(BaseModel):
    plan: str = Field(description="Plan to show the user, formatted as numbered steps")

    @field_validator("plan", mode="before")
    @classmethod
    def coerce_list_to_str(cls, v):
        if isinstance(v, list):
            return "\n".join(str(item) for item in v)
        return v


def make_show_plan_tool(bot: Bot, chat_id: int):
    @tool(args_schema=ShowPlanInput)
    async def show_plan(plan: str) -> str:
        """Show the current plan to the user in Telegram. Call this before starting execution and after updating the plan."""
        formatted = f"<b>Plan:</b>\n{escape(plan)}"
        try:
            for chunk in split_message(formatted):
                await bot.send_message(chat_id, chunk)
        except Exception:
            logger.warning("Failed to send plan to chat %s", chat_id)
            return "Failed to send plan to user, but continuing execution."
        return "Plan shown to user successfully."

    return show_plan
