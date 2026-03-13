from __future__ import annotations

import asyncio
import logging
import time

import docker
from docker.errors import ImageNotFound

from src.config import Settings
from src.db.models import ExecutionResult

logger = logging.getLogger(__name__)


class SandboxManager:
    def __init__(self, settings: Settings) -> None:
        self.client = docker.from_env()
        self.image = settings.docker_sandbox_image
        self.default_timeout = settings.docker_execution_timeout
        self.memory_limit = settings.docker_memory_limit
        self.cpu_quota = settings.docker_cpu_quota
        self.network_disabled = settings.docker_network_disabled

    async def execute(
        self,
        command: str,
        workspace_path: str,
        timeout: int | None = None,
    ) -> ExecutionResult:
        timeout = min(timeout or self.default_timeout, 120)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._run_sync, command, workspace_path, timeout
        )

    def _run_sync(
        self, command: str, workspace_path: str, timeout: int
    ) -> ExecutionResult:
        start = time.monotonic()
        try:
            container = self.client.containers.run(
                image=self.image,
                command=["bash", "-c", command],
                volumes={
                    workspace_path: {"bind": "/workspace", "mode": "rw"},
                },
                working_dir="/workspace",
                mem_limit=self.memory_limit,
                cpu_quota=self.cpu_quota,
                network_disabled=self.network_disabled,
                cap_drop=["ALL"],
                security_opt=["no-new-privileges"],
                tmpfs={"/tmp": "size=100M"},
                user="sandbox",
                detach=True,
                stdout=True,
                stderr=True,
                labels={"agent": "sandbox"},
            )
        except ImageNotFound:
            return ExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=f"Docker image '{self.image}' not found. "
                f"Build it: docker build -t {self.image} -f Dockerfile.sandbox .",
                duration_seconds=0.0,
            )
        except Exception as e:
            return ExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=f"Failed to create container: {e}",
                duration_seconds=time.monotonic() - start,
            )

        timed_out = False
        try:
            result = container.wait(timeout=timeout)
            exit_code = result.get("StatusCode", -1)
        except Exception:
            logger.warning("Container timed out, killing")
            try:
                container.kill()
            except Exception:
                pass
            timed_out = True
            exit_code = -1

        stdout = container.logs(stdout=True, stderr=False).decode(
            "utf-8", errors="replace"
        )
        stderr = container.logs(stdout=False, stderr=True).decode(
            "utf-8", errors="replace"
        )
        duration = time.monotonic() - start

        try:
            container.remove(force=True)
        except Exception:
            pass

        return ExecutionResult(
            exit_code=exit_code,
            stdout=stdout[:50_000],
            stderr=stderr[:20_000],
            timed_out=timed_out,
            duration_seconds=round(duration, 2),
        )

    def cleanup_stale(self) -> int:
        removed = 0
        for c in self.client.containers.list(
            all=True, filters={"label": "agent=sandbox"}
        ):
            try:
                c.remove(force=True)
                removed += 1
            except Exception:
                pass
        return removed
