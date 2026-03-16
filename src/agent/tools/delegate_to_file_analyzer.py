from __future__ import annotations

import logging
import os
import shutil
import tempfile

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.agent.core import build_file_analyzer_agent, build_llm
from src.agent.summarizer import summarize_text
from src.config import Settings
from src.sandbox.manager import SandboxManager

logger = logging.getLogger(__name__)


class DelegateToFileAnalyzerInput(BaseModel):
    task_description: str = Field(description="What to analyze in the file")
    file_path: str = Field(description="Absolute path to the uploaded file")


def make_delegate_to_file_analyzer_tool(
    settings: Settings,
    sandbox: SandboxManager,
):
    @tool(args_schema=DelegateToFileAnalyzerInput)
    async def delegate_to_file_analyzer(task_description: str, file_path: str) -> str:
        """Delegate file analysis (PDF, CSV, TXT, Excel) to the File Analyzer agent."""
        tmpdir = tempfile.mkdtemp(prefix="analyzer_ws_")
        try:
            # Path traversal protection
            basename = os.path.basename(file_path)
            safe_name = os.path.normpath(basename)
            if safe_name.startswith("..") or safe_name.startswith("/"):
                return "Error: invalid file path."

            # Copy file to workspace
            src_path = os.path.abspath(file_path)
            if not os.path.exists(src_path):
                return f"Error: file not found: {file_path}"

            dst_path = os.path.join(tmpdir, safe_name)
            shutil.copy2(src_path, dst_path)

            analyzer = build_file_analyzer_agent(
                settings=settings,
                sandbox=sandbox,
                workspace_path=tmpdir,
            )
            result = await analyzer.ainvoke({
                "input": f"Analyze '/workspace/{safe_name}'. User request: {task_description}",
            })
            output = result.get("output", "File analyzer produced no output.")

            # Summarize if too long
            if len(output) > 3000:
                try:
                    summary_llm = build_llm(settings, react_mode=False)
                    output = await summarize_text(summary_llm, output)
                except Exception:
                    output = output[:3000] + "\n... (truncated)"

            return output
        except Exception as e:
            logger.exception("File analyzer failed")
            return f"File analysis error: {e}"
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    return delegate_to_file_analyzer
