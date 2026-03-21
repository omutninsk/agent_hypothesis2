from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.config import Settings
from src.db.repositories.knowledge import KnowledgeRepository
from src.db.repositories.memory import MemoryRepository
from src.db.repositories.tasks import TasksRepository
from src.services.task_runner import TaskRunner
from src.transport.manager import ConnectionManager
from src.web.routes import chat, prompt_blocks, prompts, settings_routes, ws


def create_web_app(
    settings: Settings,
    task_runner: TaskRunner,
    task_repo: TasksRepository,
    memory_repo: MemoryRepository,
    knowledge_repo: KnowledgeRepository,
    connection_manager: ConnectionManager,
) -> FastAPI:
    app = FastAPI(title="Agent Hypothesis 2", version="0.1.0")

    # Shared state
    app.state.settings = settings
    app.state.task_runner = task_runner
    app.state.task_repo = task_repo
    app.state.memory_repo = memory_repo
    app.state.knowledge_repo = knowledge_repo
    app.state.connection_manager = connection_manager

    # Routes
    app.include_router(ws.router)
    app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
    app.include_router(prompts.router, prefix="/api/prompts", tags=["prompts"])
    app.include_router(settings_routes.router, prefix="/api/settings", tags=["settings"])
    app.include_router(prompt_blocks.router, prefix="/api/prompt-blocks", tags=["prompt-blocks"])

    # Static files
    static_dir = Path(__file__).parent / "static"
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app
