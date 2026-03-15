from __future__ import annotations

import json
import logging

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message

from src.bot.formatters import code_block, escape, truncate
from src.db.repositories.skills import SkillsRepository
from src.services.skill_executor import SkillExecutor

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("skills"))
async def handle_skills(
    message: Message, skill_repo: SkillsRepository
) -> None:
    skills = await skill_repo.list_all()
    if not skills:
        await message.reply("No skills saved yet.")
        return
    lines = []
    for s in skills:
        line = f"<b>{escape(s.name)}</b> — {escape(s.description)}"
        if s.input_schema:
            props = s.input_schema.get("properties", {})
            if props:
                params = ", ".join(props.keys())
                line += f"\n  Input: {escape(params)}"
        lines.append(line)
    await message.reply(truncate("\n".join(lines)))


@router.message(Command("run"))
async def handle_run(
    message: Message,
    bot: Bot,
    skill_repo: SkillsRepository,
    skill_executor: SkillExecutor,
) -> None:
    text = (message.text or "").removeprefix("/run").strip()
    parts = text.split(maxsplit=1)
    if not parts:
        await message.reply(
            'Usage: /run &lt;skill_name&gt; [json_input]\n'
            'Example: /run fetch_url {"url": "https://example.com"}'
        )
        return

    skill_name = parts[0]
    input_json = parts[1] if len(parts) > 1 else "{}"

    try:
        json.loads(input_json)
    except json.JSONDecodeError:
        await message.reply("Error: second argument must be valid JSON.")
        return

    skill = await skill_repo.get_by_name(skill_name)
    if not skill:
        await message.reply(
            f"Skill '<b>{escape(skill_name)}</b>' not found. Use /skills to list."
        )
        return

    await message.reply(f"Running <b>{escape(skill_name)}</b>...")

    result = await skill_executor.execute(skill, input_json)
    output_parts = []
    if result.stdout:
        output_parts.append(result.stdout)
    if result.stderr:
        output_parts.append(f"STDERR:\n{result.stderr}")
    if result.timed_out:
        output_parts.append("TIMED OUT")
    output_parts.append(f"Exit code: {result.exit_code}")

    await message.reply(code_block("\n".join(output_parts)))
