FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy all source needed for install
COPY pyproject.toml ./
COPY src/ ./src/
COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY entrypoint.sh ./

# Install project + dependencies
RUN pip install --no-cache-dir . && \
    chmod +x entrypoint.sh && \
    mkdir -p /tmp/agent_workspaces /app/skills

ENTRYPOINT ["./entrypoint.sh"]
