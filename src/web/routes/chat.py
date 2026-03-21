from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.db.models import TaskCreate, TaskStatus
from src.transport.web import WebTransport

router = APIRouter()
logger = logging.getLogger(__name__)

_WEB_CHAT_ID = 0


class SendRequest(BaseModel):
    message: str


@router.post("/send")
async def send_message(body: SendRequest, request: Request) -> dict:
    task_runner = request.app.state.task_runner
    task_repo = request.app.state.task_repo
    cm = request.app.state.connection_manager
    user_id = request.app.state.web_user_id

    task = await task_repo.create(
        TaskCreate(
            user_id=user_id,
            chat_id=_WEB_CHAT_ID,
            description=body.message,
        )
    )

    transport = WebTransport(cm)

    bg = asyncio.create_task(
        task_runner.run(task=task, transport=transport),
        name=f"task-{task.id}",
    )
    task_runner.register(task.id, bg)

    return {"task_id": str(task.id), "status": "started"}


@router.get("/history")
async def get_history(request: Request) -> dict:
    task_repo = request.app.state.task_repo
    user_id = request.app.state.web_user_id
    tasks = await task_repo.get_recent_completed(
        user_id, _WEB_CHAT_ID, limit=50
    )
    return {
        "tasks": [
            {
                "id": str(t.id),
                "description": t.description,
                "status": t.status.value,
                "result": t.result,
                "created_at": t.created_at.isoformat(),
            }
            for t in tasks
        ]
    }


@router.get("/status")
async def get_status(request: Request) -> dict:
    task_runner = request.app.state.task_runner
    active_ids = task_runner.active_task_ids()
    return {
        "active_tasks": [str(tid) for tid in active_ids],
        "count": len(active_ids),
    }


@router.post("/stop")
async def stop_all(request: Request) -> dict:
    task_runner = request.app.state.task_runner
    cancelled = task_runner.cancel_all()
    return {"cancelled": cancelled}
