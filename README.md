# Agent Hypothesis 2

AI-agent system with Telegram bot interface, Docker sandbox for code execution, and reusable skills registry.

The agent receives coding tasks via Telegram, writes and debugs Python code autonomously in isolated Docker containers, then saves working solutions as reusable skills.

## Prerequisites

- Docker Engine 24+ and Docker Compose v2+
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))
- An LLM API key (OpenAI-compatible endpoint)

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env: set LLM_API_KEY and TELEGRAM_BOT_TOKEN

# 2. Start everything
make up

# 3. Check logs
make logs
```

The first run builds Docker images (app + sandbox) and runs database migrations automatically.

## Commands

| Command        | Description                               |
|----------------|-------------------------------------------|
| `make up`      | Build images and start all services       |
| `make down`    | Stop all services                         |
| `make logs`    | Follow logs from all services             |
| `make build`   | Build images without starting             |
| `make migrate` | Run database migrations manually          |
| `make clean`   | Stop services and remove all data         |
| `make rebuild` | Clean everything and rebuild from scratch |
| `make shell`   | Open a shell in the app container         |

## Telegram Bot Commands

| Command                | Description                                |
|------------------------|--------------------------------------------|
| `/code <description>`  | Start a coding task                        |
| `/skills`              | List all saved skills                      |
| `/run <name> [json]`   | Run a skill with optional JSON input       |
| `/status`              | Show active tasks                          |
| `/stop`                | Cancel the current task                    |

## Architecture

```
Telegram
   |
   v
+--------+     docker.sock     +---------+
|  App   | ------------------> | Sandbox | (ephemeral containers)
| aiogram|                     | Python  |
+---+----+                     +---------+
    |
    v
+----------+
| Postgres |
+----------+
```

- **App** -- Telegram bot + two-tier LangChain agent (Supervisor + Coder). Runs in a container with Docker socket access.
- **Sandbox** -- Isolated Python 3.12 containers for code execution. Built as `agent-sandbox:latest`, created on demand per task.
- **PostgreSQL** -- Stores tasks, skills (with proto schemas), and conversation history.

## Project Structure

```
├── Dockerfile              # Main app image
├── Dockerfile.sandbox      # Sandbox image (pandas, numpy, etc.)
├── docker-compose.yml      # All services
├── Makefile                # Automation commands
├── entrypoint.sh           # DB wait + migrations + app start
├── alembic.ini             # Alembic config
├── alembic/                # Database migrations
├── pyproject.toml          # Python dependencies
└── src/
    ├── main.py             # Application entrypoint
    ├── config.py           # Settings (pydantic-settings)
    ├── agent/
    │   ├── core.py         # ReactAgent + coder builder
    │   ├── supervisor.py   # Supervisor agent builder
    │   ├── prompts.py      # System prompts
    │   ├── callbacks.py    # Telegram progress updates
    │   └── tools/          # Agent tools (6 coder + 3 supervisor)
    ├── bot/
    │   ├── app.py          # Bot + Dispatcher factory
    │   ├── middlewares.py   # Auth middleware
    │   └── handlers/       # /code, /skills, /run, /status
    ├── db/
    │   ├── models.py       # Pydantic models
    │   ├── connection.py   # asyncpg pool
    │   └── repositories/   # Skills, Tasks, Conversations
    ├── sandbox/
    │   ├── manager.py      # Docker container lifecycle
    │   └── workspace.py    # Temp directory management
    └── services/
        ├── task_runner.py   # Task orchestration
        └── skill_executor.py # Direct skill execution
```

## Environment Variables

| Variable                     | Required | Description                              |
|------------------------------|----------|------------------------------------------|
| `LLM_API_KEY`               | Yes      | API key for the LLM provider             |
| `LLM_BASE_URL`              | No       | LLM API base URL                         |
| `LLM_MODEL`                 | No       | Model name                               |
| `TELEGRAM_BOT_TOKEN`        | Yes      | Telegram bot token                       |
| `TELEGRAM_ALLOWED_USER_IDS` | No       | JSON array of allowed user IDs (empty = all) |
| `POSTGRES_DSN`              | No       | PostgreSQL connection string             |
| `DOCKER_SANDBOX_IMAGE`      | No       | Sandbox Docker image name                |
| `DOCKER_EXECUTION_TIMEOUT`  | No       | Max seconds for sandbox execution        |
| `LOG_LEVEL`                 | No       | Logging level (DEBUG, INFO, WARNING)     |

## Notes

- The app container requires Docker socket access (`/var/run/docker.sock`) to create sandbox containers.
- Workspace temp directories are bind-mounted at `/tmp/agent_workspaces` for host Docker daemon access.
- On macOS with Docker Desktop, you may need to adjust the workspace volume path in `docker-compose.yml` to a path within Docker Desktop's file sharing settings.
- If you get "permission denied" on the Docker socket, check the socket GID on your host (`stat -c %g /var/run/docker.sock`) and adjust the `docker` group GID in the `Dockerfile` accordingly.
