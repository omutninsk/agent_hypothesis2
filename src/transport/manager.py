from __future__ import annotations

import asyncio
import logging
from typing import Any

from starlette.websockets import WebSocket, WebSocketState

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections grouped by chat_id."""

    def __init__(self) -> None:
        self._connections: dict[int, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, chat_id: int, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.setdefault(chat_id, []).append(ws)
        logger.info("WebSocket connected: chat_id=%d (total=%d)", chat_id, len(self._connections.get(chat_id, [])))

    async def disconnect(self, chat_id: int, ws: WebSocket) -> None:
        async with self._lock:
            conns = self._connections.get(chat_id, [])
            if ws in conns:
                conns.remove(ws)
            if not conns:
                self._connections.pop(chat_id, None)

    async def send_to_chat(self, chat_id: int, data: dict[str, Any]) -> None:
        async with self._lock:
            conns = self._connections.get(chat_id, [])
            dead: list[WebSocket] = []
            for ws in conns:
                try:
                    if ws.client_state == WebSocketState.CONNECTED:
                        await ws.send_json(data)
                    else:
                        dead.append(ws)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                if ws in conns:
                    conns.remove(ws)
            if not conns:
                self._connections.pop(chat_id, None)
