from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.db.models import ScheduledTaskCreate
from src.db.repositories.scheduled_tasks import ScheduledTasksRepository


class ScheduleTaskInput(BaseModel):
    description: str = Field(description="What the agent should do when the task runs")
    delay_minutes: int = Field(
        default=0,
        description="Minutes to wait before first run (0 = as soon as possible)",
    )
    interval_minutes: int = Field(
        default=0,
        description="Repeat interval in minutes (0 = run once, no repeat)",
    )


def make_schedule_task_tool(
    scheduled_repo: ScheduledTasksRepository, user_id: int, chat_id: int
):
    @tool(args_schema=ScheduleTaskInput)
    async def schedule_task(
        description: str, delay_minutes: int = 0, interval_minutes: int = 0
    ) -> str:
        """Propose a scheduled task (one-shot or recurring). The task is created as PENDING and will NOT run until the user confirms it. You MUST present the proposal to the user and ask for confirmation. You can also use this proactively if you decide the user needs regular data updates."""
        active_count = await scheduled_repo.count_active(user_id)
        if active_count >= 20:
            return f"Error: you already have {active_count} active scheduled tasks (limit 20). Cancel some first."

        st = ScheduledTaskCreate(
            user_id=user_id,
            chat_id=chat_id,
            description=description,
            interval_minutes=interval_minutes if interval_minutes > 0 else None,
            delay_minutes=max(delay_minutes, 0),
        )
        created = await scheduled_repo.create(st)

        kind = f"every {interval_minutes} min" if interval_minutes > 0 else "one-shot"
        delay_info = f"after {delay_minutes} min delay" if delay_minutes > 0 else "immediately after confirmation"
        return (
            f"PROPOSED scheduled task #{created.id} ({kind}): '{description}'. "
            f"First run: {delay_info}. "
            f"STATUS: PENDING CONFIRMATION. "
            f"Tell the user about this proposal and ask them to confirm. "
            f"When user confirms, call confirm_scheduled_task with task_id={created.id}."
        )

    return schedule_task
