from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.requests import Request

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws/{chat_id}")
async def websocket_endpoint(websocket: WebSocket, chat_id: int) -> None:
    cm = websocket.app.state.connection_manager
    await cm.connect(chat_id, websocket)
    try:
        while True:
            # Keep connection alive; ignore incoming messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await cm.disconnect(chat_id, websocket)
