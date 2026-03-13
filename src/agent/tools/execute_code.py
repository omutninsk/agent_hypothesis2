from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.sandbox.manager import SandboxManager


class ExecuteCodeInput(BaseModel):
    command: str = Field(
        description="Shell command to run in Docker, e.g. 'python /workspace/main.py' or 'pip install pandas'"
    )
    timeout: int = Field(default=60, description="Timeout in seconds (max 120)")


def make_execute_code_tool(sandbox: SandboxManager, workspace_path: str):
    @tool(args_schema=ExecuteCodeInput)
    async def execute_code(command: str, timeout: int = 60) -> str:
        """Execute a shell command inside an isolated Docker container.
        Files are at /workspace. Example: python /workspace/main.py"""
        timeout = min(timeout, 120)
        result = await sandbox.execute(
            command=command,
            workspace_path=workspace_path,
            timeout=timeout,
        )
        parts = []
        if result.stdout:
            parts.append(f"STDOUT:\n{result.stdout[:5000]}")
        if result.stderr:
            parts.append(f"STDERR:\n{result.stderr[:3000]}")
        parts.append(f"EXIT_CODE: {result.exit_code}")
        if result.timed_out:
            parts.append("TIMED OUT")
        parts.append(f"Duration: {result.duration_seconds}s")
        return "\n\n".join(parts)

    return execute_code
