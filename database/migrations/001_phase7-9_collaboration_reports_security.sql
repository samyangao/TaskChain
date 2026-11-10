-- ===========================================================================
-- TaskChain — Phase 7, 8 and 9 database setup
-- ===========================================================================
-- Run this whole file in pgAdmin (Query Tool) against the same PostgreSQL
-- database that the TaskChain Flask app uses.
--
-- It is safe to run more than once:
--   * every table is created with IF NOT EXISTS
--   * every index is created with IF NOT EXISTS
--   * every column is added with IF NOT EXISTS
--
-- Existing tasks, users, comments and audit history are not modified.
-- ===========================================================================

CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- Phase 7: collaboration
--  * task_comments            already existed; now indexed by task and time
--  * task_comment_mentions    who a comment @mentioned (only people who can open the task)
--  * task_watchers            people following a task; they are told about its activity
--  * task_subtasks            a checklist of smaller steps inside a task ("3 / 5 completed")
--  * task_dependencies        "task B cannot start until task A reaches <required_state>"
--      required_state: 'for_verification' = A's work is done and submitted for review (or later)
--                      'completed'        = A is verified/completed
--      released_at is when the "no longer blocked" notice was sent (reset if A stops being done)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_task_comments_task ON task_comments(task_id, created_at);

CREATE TABLE IF NOT EXISTS task_comment_mentions (
    comment_id UUID NOT NULL REFERENCES task_comments(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY (comment_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_task_comment_mentions_user ON task_comment_mentions(user_id);

CREATE TABLE IF NOT EXISTS task_watchers (
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    added_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (task_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_task_watchers_user ON task_watchers(user_id);

CREATE TABLE IF NOT EXISTS task_subtasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    title VARCHAR(160) NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    is_done BOOLEAN NOT NULL DEFAULT FALSE,
    done_at TIMESTAMPTZ,
    done_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT task_subtasks_title_check CHECK (btrim(title) <> '')
);
CREATE INDEX IF NOT EXISTS idx_task_subtasks_task ON task_subtasks(task_id, position);

CREATE TABLE IF NOT EXISTS task_dependencies (
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    depends_on_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    required_state VARCHAR(20) NOT NULL DEFAULT 'completed',
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    released_at TIMESTAMPTZ,
    PRIMARY KEY (task_id, depends_on_id),
    CONSTRAINT task_dependencies_not_self CHECK (task_id <> depends_on_id),
    CONSTRAINT task_dependencies_state_check CHECK (required_state IN ('for_verification','completed'))
);
CREATE INDEX IF NOT EXISTS idx_task_dependencies_on ON task_dependencies(depends_on_id);

-- ---------------------------------------------------------------------------
-- Phase 8: reports and exports
-- Reports only read existing data; these indexes keep filtered reports fast.
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_tasks_assigned_status ON tasks(assigned_to, status);
CREATE INDEX IF NOT EXISTS idx_tasks_category_created ON tasks(category, created_at);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);
CREATE INDEX IF NOT EXISTS idx_task_custody_holder ON task_custody(holder_id, started_at);

-- ---------------------------------------------------------------------------
-- Phase 9: account security
--  * session_version       bumped by "Sign out everywhere" and password changes;
--                          every session cookie carries the value it was created
--                          with, so old cookies stop working immediately.
--  * totp_*                optional time-based one-time-password (2FA).
--                          Secrets are stored encrypted with pgp_sym_encrypt;
--                          the application key is derived from FLASK_SECRET_KEY.
--  * password_changed_at   shown on the Security page.
-- ---------------------------------------------------------------------------
ALTER TABLE users ADD COLUMN IF NOT EXISTS session_version INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_enabled BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_secret BYTEA;
ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_pending_secret BYTEA;
ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_last_step BIGINT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_enabled_at TIMESTAMPTZ;

-- Helpful for administrator views of accounts with 2FA enabled.
CREATE INDEX IF NOT EXISTS idx_users_totp_enabled ON users(totp_enabled);

-- ===========================================================================
-- Done. Reload/restart the TaskChain Flask server after running this file.
-- ===========================================================================
