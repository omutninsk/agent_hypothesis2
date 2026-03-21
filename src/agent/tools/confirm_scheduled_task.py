from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.db.repositories.scheduled_tasks import ScheduledTasksRepository


class ConfirmScheduledTaskInput(BaseModel):
    task_id: int = Field(description="ID of the scheduled task to confirm and activate")


def make_confirm_scheduled_task_tool(
    scheduled_repo: ScheduledTasksRepository, user_id: int
):
    @tool(args_schema=ConfirmScheduledTaskInput)
    async def confirm_scheduled_task(task_id: int) -> str:
        """Activate a pending scheduled task after user has confirmed it. Only call this when the user explicitly agreed to the proposed schedule."""
        ok = await scheduled_repo.confirm(task_id, user_id)
        if ok:
            return f"Scheduled task #{task_id} confirmed and activated. It will run on schedule."
        return f"Scheduled task #{task_id} not found, already active, or belongs to another user."

    return confirm_scheduled_task
