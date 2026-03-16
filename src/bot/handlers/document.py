from __future__ import annotations

import logging
import os
import tempfile

from aiogram import Bot, F, Router
from aiogram.types import Message

from src.bot.handlers.code import start_task
from src.db.repositories.tasks import TasksRepository
from src.services.task_runner import TaskRunner

router = Router()
logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".csv", ".xlsx", ".xls", ".json", ".xml"}
_MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


@router.message(F.document)
async def handle_document(
    message: Message,
    bot: Bot,
    task_runner: TaskRunner,
    task_repo: TasksRepository,
) -> None:
    """Handle uploaded documents — download and route to file analyzer."""
    doc = message.document
    if not doc:
        return

    # Validate file size
    if doc.file_size and doc.file_size > _MAX_FILE_SIZE:
        await message.reply("File too large. Maximum size: 20 MB.")
        return

    # Validate extension
    filename = doc.file_name or "unknown"
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    if ext not in _SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(_SUPPORTED_EXTENSIONS))
        await message.reply(f"Unsupported file type: {ext}\nSupported: {supported}")
        return

    # Download file
    try:
        file = await bot.get_file(doc.file_id)
        if not file.file_path:
            await message.reply("Failed to get file from Telegram.")
            return

        tmpdir = tempfile.mkdtemp(prefix="upload_")
        local_path = os.path.join(tmpdir, filename)
        await bot.download_file(file.file_path, local_path)
    except Exception:
        logger.exception("Failed to download file")
        await message.reply("Failed to download the file.")
        return

    # Build task description
    caption = (message.caption or "").strip()
    user_request = caption if caption else "Analyze this file and summarize its contents."
    description = (
        f"[FILE_UPLOAD: {local_path}]\n"
        f"Filename: {filename}\n"
        f"User request: {user_request}"
    )

    await start_task(
        description=description,
        message=message,
        bot=bot,
        task_runner=task_runner,
        task_repo=task_repo,
    )
