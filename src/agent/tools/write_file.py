from __future__ import annotations

import os

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class WriteFileInput(BaseModel):
    filename: str = Field(description="Relative path, e.g. 'main.py' or 'utils/helpers.py'")
    content: str = Field(description="Full file content")


def make_write_file_tool(workspace_path: str):
    @tool(args_schema=WriteFileInput)
    def write_file(filename: str, content: str) -> str:
        """Write a file to the workspace. Creates directories if needed."""
        safe = os.path.normpath(filename)
        if safe.startswith("..") or safe.startswith("/"):
            return "Error: path traversal not allowed."
        full = os.path.join(workspace_path, safe)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)
        return f"Written: {safe} ({len(content)} bytes)"

    return write_file
