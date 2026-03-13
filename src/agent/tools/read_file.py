from __future__ import annotations

import os

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class ReadFileInput(BaseModel):
    filename: str = Field(description="Relative path to file in workspace")


def make_read_file_tool(workspace_path: str):
    @tool(args_schema=ReadFileInput)
    def read_file(filename: str) -> str:
        """Read a file from the workspace."""
        safe = os.path.normpath(filename)
        if safe.startswith("..") or safe.startswith("/"):
            return "Error: path traversal not allowed."
        full = os.path.join(workspace_path, safe)
        if not os.path.exists(full):
            return f"Error: file '{safe}' not found."
        with open(full) as f:
            content = f.read()
        if len(content) > 10_000:
            return content[:10_000] + "\n... (truncated)"
        return content

    return read_file
