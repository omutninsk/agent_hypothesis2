# CLAUDE.md

## Project Overview

Autonomous LLM agent with a Telegram bot (aiogram 3), Docker sandbox for code execution, and PostgreSQL for persistence.

- **Two-level agent system**: Supervisor (planning/routing) → Coder (writing/debugging code)
- **Custom text-based ReAct loop** in `src/agent/core.py` (not langgraph prebuilt)
- No paid API keys — the agent uses scraping and free APIs

## Commands

```bash
make up        # docker compose up --build -d
make down      # stop
make logs      # follow logs
make rebuild   # clean volumes + rebuild
make migrate   # alembic upgrade head
make shell     # exec into app container
pytest         # tests (scaffold in tests/, no tests yet)
```

## Architecture

```
src/
├── main.py              # entrypoint
├── config.py            # pydantic-settings from .env
├── agent/
│   ├── core.py          # ReAct loop
│   ├── supervisor.py    # Supervisor agent
│   ├── prompts.py       # system prompts
│   ├── callbacks.py     # LLM callbacks
│   └── tools/           # tool definitions
├── bot/
│   ├── app.py           # bot startup
│   ├── middlewares.py   # aiogram middlewares
│   ├── formatters.py    # message formatting
│   └── handlers/        # message/command handlers
├── db/
│   ├── models.py        # SQLAlchemy models
│   ├── connection.py    # async engine/session
│   └── repositories/    # data access layer
├── sandbox/
│   ├── manager.py       # Docker container lifecycle
│   └── workspace.py     # workspace file management
└── services/
    ├── task_runner.py    # orchestrates agent tasks
    └── skill_executor.py # runs saved skills
```

## Code Conventions

- `from __future__ import annotations` in every file
- Async everywhere (asyncpg, aiogram 3, tool functions)
- Docker SDK is sync — wrap in `run_in_executor`
- Tool factory pattern: `make_<tool_name>_tool(repo, user_id)` → returns a `@tool` function
- Pydantic `BaseModel` for tool input schemas with `Field(description=...)`
- `snake_case` files/functions, `PascalCase` classes, `UPPER_SNAKE_CASE` constants
- Private methods: `_prefix`

## Tech Stack & Gotchas

- **Python 3.12** (Dockerfile: `python:3.12-slim`)
- **LLM**: OpenAI-compatible endpoint (`qwen3_4b_instruct` @ `aisupervisor.ru/v1`)
- **DB**: PostgreSQL 16 + asyncpg + alembic (psycopg3 for migrations, NOT psycopg2)
- `alembic.ini` connection string: `postgresql+psycopg://` (not `psycopg2`)
- **Sandbox**: ephemeral Docker containers, `cap_drop=ALL`, `no-new-privileges`

## Key Patterns

- **Memory** (key-value, UPSERT) and **Knowledge** (append-only, FTS)
- Memory prefixes: `_ctx:*` — task context (auto-cleanup), `_insight:*` — permanent insights
- **Skills**: JSON stdin → stdout, saved to DB + filesystem
- **aiogram 3 DI**: `dp["key"] = value` → auto-injected into handler kwargs by matching param name

## Security

- Path traversal protection: `os.path.normpath` + check for `..` and leading `/`
- Skill names validated: regex `^[a-z][a-z0-9_]*$`
- Docker sandbox: memory limit 512m, CPU quota, network can be disabled
- `.env` with secrets — listed in `.gitignore`
