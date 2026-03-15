import asyncio
import logging

from src.config import Settings
from src.utils.logging import setup_logging
from src.db.connection import DatabasePool
from src.db.repositories.knowledge import KnowledgeRepository
from src.db.repositories.memory import MemoryRepository
from src.db.repositories.skills import SkillsRepository
from src.db.repositories.tasks import TasksRepository
from src.db.repositories.conversations import ConversationsRepository
from src.sandbox.manager import SandboxManager
from src.services.task_runner import TaskRunner
from src.services.skill_executor import SkillExecutor
from src.bot.app import create_bot

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = Settings()
    setup_logging(settings.log_level)
    logger.info("Starting agent system...")

    # Database
    db = DatabasePool()
    await db.connect(settings.postgres_dsn)
    logger.info("Database connected")

    skill_repo = SkillsRepository(db.pool)
    task_repo = TasksRepository(db.pool)
    memory_repo = MemoryRepository(db.pool)
    knowledge_repo = KnowledgeRepository(db.pool)
    conversation_repo = ConversationsRepository(db.pool)

    # Recover tasks left in RUNNING state from previous run
    recovered = await task_repo.recover_orphaned()
    if recovered:
        logger.warning("Recovered %d orphaned tasks (marked as FAILED)", recovered)

    # Sandbox
    sandbox = SandboxManager(settings)

    # Services
    task_runner = TaskRunner(
        settings=settings,
        sandbox_manager=sandbox,
        task_repo=task_repo,
        skill_repo=skill_repo,
        memory_repo=memory_repo,
        knowledge_repo=knowledge_repo,
        conversation_repo=conversation_repo,
    )
    skill_executor = SkillExecutor(
        sandbox_manager=sandbox,
        skill_repo=skill_repo,
        settings=settings,
    )

    # Bot
    bot, dp = create_bot(settings)

    dp["task_runner"] = task_runner
    dp["skill_executor"] = skill_executor
    dp["skill_repo"] = skill_repo
    dp["task_repo"] = task_repo
    dp["memory_repo"] = memory_repo
    dp["knowledge_repo"] = knowledge_repo
    dp["settings"] = settings

    logger.info("Starting Telegram bot polling...")
    try:
        await dp.start_polling(bot)
    finally:
        await db.disconnect()
        logger.info("Shutdown complete")


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
