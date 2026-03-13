CREATE TABLE IF NOT EXISTS skills (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(128) UNIQUE NOT NULL,
    description TEXT NOT NULL,
    code        TEXT NOT NULL,
    language    VARCHAR(16) NOT NULL DEFAULT 'python',
    entry_point VARCHAR(128) NOT NULL DEFAULT 'main.py',
    dependencies TEXT[] DEFAULT '{}',
    created_by  BIGINT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tags        TEXT[] DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         BIGINT NOT NULL,
    chat_id         BIGINT NOT NULL,
    description     TEXT NOT NULL,
    status          VARCHAR(32) NOT NULL DEFAULT 'pending',
    result          TEXT,
    skill_id        INTEGER REFERENCES skills(id),
    iteration       INTEGER NOT NULL DEFAULT 0,
    max_iterations  INTEGER NOT NULL DEFAULT 10,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS conversation_history (
    id          SERIAL PRIMARY KEY,
    task_id     UUID REFERENCES tasks(id) ON DELETE CASCADE,
    role        VARCHAR(16) NOT NULL,
    content     TEXT NOT NULL,
    tool_name   VARCHAR(64),
    tool_call_id VARCHAR(64),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_skills_name ON skills(name);
CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_conversation_task_id ON conversation_history(task_id);
