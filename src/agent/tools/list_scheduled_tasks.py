from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel

from src.db.repositories.scheduled_tasks import ScheduledTasksRepository


class ListScheduledTasksInput(BaseModel):
    pass


def make_list_scheduled_tasks_tool(
    scheduled_repo: ScheduledTasksRepository, user_id: int
):
    @tool(args_schema=ListScheduledTasksInput)
    async def list_scheduled_tasks() -> str:
        """List all scheduled/recurring tasks for the current user (active and pending confirmation)."""
        active = await scheduled_repo.list_by_user(user_id, active_only=True)
        pending = await scheduled_repo.list_pending(user_id)

        if not active and not pending:
            return "No scheduled tasks."

        lines: list[str] = []

        if pending:
            lines.append(f"PENDING CONFIRMATION ({len(pending)}):")
            for t in pending:
                kind = f"every {t.interval_minutes} min" if t.interval_minutes else "one-shot"
                lines.append(
                    f"  #{t.id} | {kind} | {t.description[:80]} "
                    f"| call confirm_scheduled_task to activate"
                )

        if active:
            lines.append(f"ACTIVE ({len(active)}):")
            for t in active:
                kind = f"every {t.interval_minutes} min" if t.interval_minutes else "one-shot"
                last = t.last_run_at.strftime("%Y-%m-%d %H:%M") if t.last_run_at else "never"
                lines.append(
                    f"  #{t.id} | {kind} | runs: {t.run_count} | "
                    f"next: {t.next_run_at.strftime('%Y-%m-%d %H:%M')} | "
                    f"last: {last} | {t.description[:80]}"
                )

        return "\n".join(lines)

    return list_scheduled_tasks
