from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from langchain_core.tools import tool
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from src.db.repositories.memory import MemoryRepository
    from src.sandbox.manager import SandboxManager

logger = logging.getLogger(__name__)


class ExportFindingsInput(BaseModel):
    filename: str = Field(
        default="findings.json",
        description="Output filename (saved in /workspace/)",
    )


def make_export_findings_tool(
    memory_repo: MemoryRepository,
    sandbox: SandboxManager,
    user_id: int,
):
    @tool(args_schema=ExportFindingsInput)
    async def export_findings(filename: str = "findings.json") -> str:
        """Export all stored findings to a JSON file in the sandbox workspace."""
        entries = await memory_repo.recall_by_prefix("_data:", user_id)
        if not entries:
            return "No findings to export."

        data = [
            {"key": e.key.removeprefix("_data:"), "content": e.content}
            for e in entries
        ]
        json_str = json.dumps(data, ensure_ascii=False, indent=2)

        # Write via sandbox
        code = (
            "import json, sys\n"
            f"data = json.loads({json_str!r})\n"
            f"with open('/workspace/{filename}', 'w', encoding='utf-8') as f:\n"
            f"    json.dump(data, f, ensure_ascii=False, indent=2)\n"
            f"print(f'Written {{len(data)}} findings to /workspace/{filename}')\n"
        )

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, sandbox.execute_code, code)
        return f"Exported {len(entries)} findings to /workspace/{filename}"

    return export_findings
