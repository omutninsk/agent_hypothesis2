from __future__ import annotations

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message

from src.bot.handlers.code import start_task
from src.db.repositories.tasks import TasksRepository
from src.services.task_runner import TaskRunner

router = Router()

_EXPLORE_FREE = (
    "EXPLORATION MODE. You have no specific user request. Instead:\n"
    "1. recall_memory to review your insights.\n"
    "2. search_skills to list existing skills.\n"
    "3. Pick ONE of these actions:\n"
    "   a) Improve or test an existing skill that might be broken.\n"
    "   b) web_search for something interesting related to your insights.\n"
    "   c) Learn something new and save_knowledge.\n"
    "4. Save any new insights with update_context(layer='insight').\n"
    "5. Final Answer: summarize what you explored and learned."
)

_EXPLORE_TOPIC = (
    "EXPLORATION MODE — topic: {topic}\n"
    "1. recall_memory to check what you already know about this topic.\n"
    "2. web_search to find useful information about: {topic}\n"
    "3. save_knowledge with what you learned.\n"
    "4. If you can build a useful skill related to this, delegate_to_coder.\n"
    "5. Save any new insights with update_context(layer='insight').\n"
    "6. Final Answer: summarize what you explored and learned about {topic}."
)


@router.message(Command("explore"))
async def handle_explore(
    message: Message,
    bot: Bot,
    task_runner: TaskRunner,
    task_repo: TasksRepository,
) -> None:
    """Handle /explore [topic] — autonomous exploration mode."""
    topic = (message.text or "").removeprefix("/explore").strip()

    if topic:
        description = _EXPLORE_TOPIC.format(topic=topic)
    else:
        description = _EXPLORE_FREE

    await start_task(
        description=description,
        message=message,
        bot=bot,
        task_runner=task_runner,
        task_repo=task_repo,
    )
