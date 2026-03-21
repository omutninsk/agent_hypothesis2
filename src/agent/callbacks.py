from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler

if TYPE_CHECKING:
    from src.transport.protocol import ChatTransport

logger = logging.getLogger(__name__)

_STATUS_MAP = {
    "write_file": "Writing file",
    "read_file": "Reading file",
    "execute_code": "Executing code",
    "save_skill": "Saving skill",
    "list_skills": "Listing skills",
    "run_skill": "Running skill",
    "search_skills": "Searching skills",
    "run_existing_skill": "Running existing skill",
    "delegate_to_coder": "Delegating to coder agent",
    "save_to_memory": "Saving to memory",
    "recall_memory": "Recalling memory",
    "web_search": "Searching the web",
    "delete_skill": "Deleting skill",
    "save_knowledge": "Saving knowledge",
    "search_knowledge": "Searching knowledge",
    "update_context": "Updating context",
    "delegate_to_file_analyzer": "Analyzing document",
    "show_plan": "Presenting plan",
}


class TransportProgressCallback(AsyncCallbackHandler):
    def __init__(self, transport: ChatTransport, chat_id: int, task_id: UUID) -> None:
        self.transport = transport
        self.chat_id = chat_id
        self.task_id = task_id
        self._step = 0

    async def on_tool_start(
        self, serialized: dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        self._step += 1
        name = serialized.get("name", "unknown")
        status = _STATUS_MAP.get(name, f"Using {name}")
        await self.transport.send_progress(
            self.chat_id, self.task_id, self._step, status
        )

    async def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        await self.transport.send_error(
            self.chat_id, self.task_id, self._step, str(error)[:500]
        )
