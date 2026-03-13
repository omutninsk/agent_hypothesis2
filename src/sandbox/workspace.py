from __future__ import annotations

import os
import shutil


class WorkspaceManager:
    def __init__(self, base_dir: str = "/tmp/agent_workspaces") -> None:
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def create(self, task_id: str) -> str:
        path = os.path.join(self.base_dir, task_id)
        os.makedirs(path, exist_ok=True)
        return path

    def destroy(self, task_id: str) -> None:
        path = os.path.join(self.base_dir, task_id)
        if os.path.exists(path):
            shutil.rmtree(path)

    def list_files(self, task_id: str) -> list[str]:
        path = os.path.join(self.base_dir, task_id)
        result = []
        for root, _dirs, files in os.walk(path):
            for f in files:
                full = os.path.join(root, f)
                result.append(os.path.relpath(full, path))
        return result

    def get_path(self, task_id: str) -> str:
        return os.path.join(self.base_dir, task_id)

    def write_file(self, task_id: str, filename: str, content: str) -> str:
        """Write a file into the task workspace. Returns the relative path."""
        safe = os.path.normpath(filename)
        if safe.startswith("..") or safe.startswith("/"):
            raise ValueError("Path traversal not allowed")
        full = os.path.join(self.base_dir, task_id, safe)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)
        return safe

    def read_file(self, task_id: str, filename: str) -> str:
        safe = os.path.normpath(filename)
        if safe.startswith("..") or safe.startswith("/"):
            raise ValueError("Path traversal not allowed")
        full = os.path.join(self.base_dir, task_id, safe)
        with open(full) as f:
            return f.read()
