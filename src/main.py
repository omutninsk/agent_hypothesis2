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
    setup_logging(settings.log_level, prompt_blocks_enabled=bool(settings.log_prompt_blocks))
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

    # Scheduled tasks repository (conditional)
    scheduled_repo = None
    if settings.feature_scheduled_tasks:
        from src.db.repositories.scheduled_tasks import ScheduledTasksRepository
        scheduled_repo = ScheduledTasksRepository(db.pool)

    # Services
    task_runner = TaskRunner(
        settings=settings,
        sandbox_manager=sandbox,
        task_repo=task_repo,
        skill_repo=skill_repo,
        memory_repo=memory_repo,
        knowledge_repo=knowledge_repo,
        conversation_repo=conversation_repo,
        scheduled_repo=scheduled_repo,
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

    # Scheduler
    if settings.feature_scheduled_tasks and scheduled_repo is not None:
        from src.services.scheduler import Scheduler
        from src.transport.telegram import TelegramTransport

        scheduler = Scheduler(
            scheduled_repo=scheduled_repo,
            task_repo=task_repo,
            task_runner=task_runner,
            transport=TelegramTransport(bot),
        )
        logger.info("Scheduled tasks feature enabled")

    # Web UI
    tasks = [dp.start_polling(bot)]

    if settings.web_enabled:
        import uvicorn

        from src.transport.manager import ConnectionManager
        from src.web.app import create_web_app

        cm = ConnectionManager()
        web_app = create_web_app(
            settings=settings,
            task_runner=task_runner,
            task_repo=task_repo,
            memory_repo=memory_repo,
            knowledge_repo=knowledge_repo,
            connection_manager=cm,
        )
        config = uvicorn.Config(
            web_app,
            host=settings.web_host,
            port=settings.web_port,
            log_level=settings.log_level.lower(),
        )
        server = uvicorn.Server(config)
        tasks.append(server.serve())
        logger.info("Web UI will be available at http://%s:%d", settings.web_host, settings.web_port)

    if settings.feature_scheduled_tasks and scheduled_repo is not None:
        tasks.append(scheduler.run_forever())

    logger.info("Starting Telegram bot polling...")
    try:
        await asyncio.gather(*tasks)
    finally:
        await db.disconnect()
        logger.info("Shutdown complete")


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
