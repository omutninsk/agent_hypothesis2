from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.db.repositories.scheduled_tasks import ScheduledTasksRepository


class CancelScheduledTaskInput(BaseModel):
    task_id: int = Field(description="ID of the scheduled task to cancel")


def make_cancel_scheduled_task_tool(
    scheduled_repo: ScheduledTasksRepository, user_id: int
):
    @tool(args_schema=CancelScheduledTaskInput)
    async def cancel_scheduled_task(task_id: int) -> str:
        """Cancel a scheduled/recurring task by its ID. Only your own tasks can be cancelled."""
        ok = await scheduled_repo.cancel(task_id, user_id)
        if ok:
            return f"Scheduled task #{task_id} cancelled."
        return f"Scheduled task #{task_id} not found or already inactive."

    return cancel_scheduled_task
