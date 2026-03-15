from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class GetCurrentDatetimeInput(BaseModel):
    timezone: str = Field(
        default="Europe/Moscow",
        description="IANA timezone, e.g. 'Europe/Moscow', 'UTC', 'US/Eastern'",
    )


def make_get_current_datetime_tool():
    @tool(args_schema=GetCurrentDatetimeInput)
    async def get_current_datetime(timezone: str = "Europe/Moscow") -> str:
        """Get the REAL current date and time. Use this EVERY TIME you need to know today's date, current time, or current year. NEVER guess the time — always call this tool."""
        try:
            tz = ZoneInfo(timezone)
        except KeyError:
            tz = ZoneInfo("UTC")
        now = datetime.now(tz)
        return now.strftime("%Y-%m-%d %H:%M:%S %Z (%A)")

    return get_current_datetime
