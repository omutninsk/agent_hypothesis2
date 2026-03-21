from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

HELP_TEXT = """<b>Agent Bot</b>

<b>Commands:</b>
/code &lt;description&gt; — start a coding task
/explore [topic] — autonomous exploration mode
/skills — list saved skills
/run &lt;name&gt; [args] — run a saved skill
/memory — show agent memories
/settings — manage agent deep settings
/status — show active tasks
/stop — cancel active tasks
/help — show this message"""


@router.message(Command("start"))
async def handle_start(message: Message) -> None:
    await message.reply(HELP_TEXT)


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    await message.reply(HELP_TEXT)
