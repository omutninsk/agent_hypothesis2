from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain_core.tools import tool
from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    from src.agent.planner import PlanState
    from src.transport.protocol import ChatTransport

logger = logging.getLogger(__name__)


class ShowPlanInput(BaseModel):
    plan: str = Field(description="Plan to show the user, formatted as numbered steps")

    @field_validator("plan", mode="before")
    @classmethod
    def coerce_list_to_str(cls, v):
        if isinstance(v, list):
            return "\n".join(str(item) for item in v)
        return v


def make_show_plan_tool(
    transport: ChatTransport,
    chat_id: int,
    plan_state: PlanState | None = None,
):
    @tool(args_schema=ShowPlanInput)
    async def show_plan(plan: str) -> str:
        """Show the current plan to the user. Call this before starting execution and after updating the plan.
        For hierarchical planning: call multiple times — first with top-level steps, then with sub-steps for each step."""
        if plan_state is not None:
            result = plan_state.submit_plan(plan)

            # Show current plan state to user
            if plan_state.finalized:
                tree = plan_state.format_tree()
                flat = plan_state.format_flat()
                msg = (
                    f"<b>Plan (hierarchical):</b>\n"
                    f"{transport.format_text(tree)}\n\n"
                    f"<b>Action list:</b>\n"
                    f"{transport.format_text(flat)}"
                )
            else:
                tree = plan_state.format_tree()
                msg = (
                    f"<b>Plan (in progress):</b>\n"
                    f"{transport.format_text(tree)}"
                )

            try:
                await transport.send_text(chat_id, msg)
            except Exception:
                logger.warning("Failed to send plan to chat %s", chat_id)

            return result

        # Fallback: no plan_state — simple display (backward compat)
        formatted = f"<b>Plan:</b>\n{transport.format_text(plan)}"
        try:
            await transport.send_text(chat_id, formatted)
        except Exception:
            logger.warning("Failed to send plan to chat %s", chat_id)
            return "Failed to send plan to user, but continuing execution."
        return "Plan shown to user successfully."

    return show_plan
