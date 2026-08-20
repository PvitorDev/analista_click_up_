CREATE TABLE IF NOT EXISTS members (
    clickup_id TEXT PRIMARY KEY,
    username TEXT,
    email TEXT,
    display_name TEXT,
    role_raw INTEGER,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS spaces (
    clickup_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS folders (
    clickup_id TEXT PRIMARY KEY,
    space_id TEXT REFERENCES spaces(clickup_id),
    name TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS lists (
    clickup_id TEXT PRIMARY KEY,
    space_id TEXT REFERENCES spaces(clickup_id),
    folder_id TEXT REFERENCES folders(clickup_id),
    name TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tasks (
    clickup_id TEXT PRIMARY KEY,
    custom_id TEXT,
    name TEXT NOT NULL,
    description TEXT,
    url TEXT,
    list_id TEXT REFERENCES lists(clickup_id),
    parent_id TEXT,
    status_raw TEXT,
    status_canonical TEXT NOT NULL,
    date_created TIMESTAMPTZ,
    date_updated TIMESTAMPTZ,
    date_closed TIMESTAMPTZ,
    due_date TIMESTAMPTZ,
    start_date TIMESTAMPTZ,
    archived BOOLEAN NOT NULL DEFAULT false,
    assignees JSONB NOT NULL DEFAULT '[]'::jsonb,
    primary_assignee_id TEXT,
    prioridade TEXT,
    contexto TEXT,
    area TEXT,
    tipo TEXT,
    last_status_seen TEXT,
    last_status_seen_at TIMESTAMPTZ,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

ALTER TABLE tasks ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_tasks_list ON tasks(list_id);
CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status_canonical);
CREATE INDEX IF NOT EXISTS idx_tasks_primary ON tasks(primary_assignee_id);
CREATE INDEX IF NOT EXISTS idx_tasks_deleted_at ON tasks(deleted_at);

CREATE TABLE IF NOT EXISTS comments (
    clickup_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(clickup_id) ON DELETE CASCADE,
    author_id TEXT,
    text TEXT,
    date TIMESTAMPTZ,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_comments_task ON comments(task_id);
CREATE INDEX IF NOT EXISTS idx_comments_author ON comments(author_id);

CREATE TABLE IF NOT EXISTS attachments (
    clickup_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(clickup_id) ON DELETE CASCADE,
    title TEXT,
    url TEXT,
    date TIMESTAMPTZ
);

-- A2: cada transição. Histórico não capturado não volta.
CREATE TABLE IF NOT EXISTS status_transitions (
    id BIGSERIAL PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(clickup_id) ON DELETE CASCADE,
    from_status TEXT,
    to_status TEXT NOT NULL,
    from_canonical TEXT,
    to_canonical TEXT NOT NULL,
    at TIMESTAMPTZ NOT NULL,
    actor_clickup_id TEXT,
    source TEXT NOT NULL,
    UNIQUE (task_id, at, to_status, source)
);

CREATE INDEX IF NOT EXISTS idx_transitions_task ON status_transitions(task_id, at);

CREATE TABLE IF NOT EXISTS custom_fields (
    task_id TEXT NOT NULL REFERENCES tasks(clickup_id) ON DELETE CASCADE,
    field_id TEXT NOT NULL,
    field_name TEXT,
    value_text TEXT,
    value_json JSONB,
    PRIMARY KEY (task_id, field_id)
);

CREATE TABLE IF NOT EXISTS sync_state (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Extração (Bloco B)
CREATE TABLE IF NOT EXISTS milestones (
    id BIGSERIAL PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(clickup_id) ON DELETE CASCADE,
    phase TEXT,
    due_on DATE,
    evidence TEXT,
    UNIQUE (task_id, phase, due_on)
);

CREATE TABLE IF NOT EXISTS dependencies (
    id BIGSERIAL PRIMARY KEY,
    from_task_id TEXT REFERENCES tasks(clickup_id) ON DELETE SET NULL,
    to_task_id TEXT REFERENCES tasks(clickup_id) ON DELETE SET NULL,
    from_person TEXT,
    to_person TEXT,
    description TEXT NOT NULL,
    evidence_task_id TEXT,
    UNIQUE (description, evidence_task_id)
);

CREATE TABLE IF NOT EXISTS risks (
    id BIGSERIAL PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(clickup_id) ON DELETE CASCADE,
    kind TEXT NOT NULL DEFAULT 'risco',
    text TEXT NOT NULL,
    UNIQUE (task_id, kind, text)
);

CREATE TABLE IF NOT EXISTS decisions (
    id BIGSERIAL PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(clickup_id) ON DELETE CASCADE,
    comment_id TEXT,
    author_id TEXT,
    text TEXT NOT NULL,
    decided_at TIMESTAMPTZ,
    UNIQUE (task_id, comment_id)
);

CREATE TABLE IF NOT EXISTS task_taxonomy (
    task_id TEXT PRIMARY KEY REFERENCES tasks(clickup_id) ON DELETE CASCADE,
    area TEXT,
    tipo TEXT,
    source TEXT
);

-- Relatórios (Bloco E)
CREATE TABLE IF NOT EXISTS reports (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    title TEXT NOT NULL DEFAULT '',
    narrative TEXT NOT NULL,
    improvements JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    generated_by TEXT,
    history_summary TEXT NOT NULL DEFAULT '',
    team_id TEXT
);

ALTER TABLE reports ADD COLUMN IF NOT EXISTS title TEXT NOT NULL DEFAULT '';
ALTER TABLE reports ADD COLUMN IF NOT EXISTS history_summary TEXT NOT NULL DEFAULT '';
ALTER TABLE reports ADD COLUMN IF NOT EXISTS team_id TEXT;
CREATE INDEX IF NOT EXISTS idx_reports_team_created ON reports (team_id, created_at DESC);

CREATE TABLE IF NOT EXISTS person_profiles (
    person_id TEXT PRIMARY KEY REFERENCES members(clickup_id) ON DELETE CASCADE,
    report_id BIGINT REFERENCES reports(id) ON DELETE CASCADE,
    strengths TEXT,
    leverage TEXT,
    next_step TEXT,
    domains JSONB,
    consistency TEXT,
    autonomy TEXT,
    load_note TEXT,
    knowledge_concentration JSONB,
    collaboration JSONB,
    communication JSONB,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Auth
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    clickup_user_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'member')),
    access_token TEXT,
    username TEXT,
    email TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

CREATE TABLE IF NOT EXISTS chat_messages (
    id BIGSERIAL PRIMARY KEY,
    clickup_user_id TEXT NOT NULL,
    author TEXT NOT NULL CHECK (author IN ('user', 'assistant')),
    content TEXT NOT NULL,
    report_id BIGINT REFERENCES reports(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS report_id BIGINT REFERENCES reports(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_created
    ON chat_messages (clickup_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_report
    ON chat_messages (clickup_user_id, report_id, created_at DESC);
