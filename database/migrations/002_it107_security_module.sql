-- ===========================================================================
-- IT 107 Secure Registration, Authentication and Monitoring module
-- ===========================================================================
-- Seed: student number 241-01803 -> D1 = 0, D2 = 3.
-- Safe to run more than once: every object uses IF NOT EXISTS / OR REPLACE.
--
-- The existing TaskChain tables stay as they are. This migration adds the
-- registration profile, one-time codes, password history, IP blocks, the
-- append-only activity log and the monitoring flags table.
-- ===========================================================================

CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- users: login identifier and lockout tier
-- Existing accounts are treated as verified so they keep working. New public
-- registrations explicitly insert is_verified = FALSE.
-- ---------------------------------------------------------------------------
ALTER TABLE users ADD COLUMN IF NOT EXISTS username CITEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS lockout_tier SMALLINT NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_failed_at TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username) WHERE username IS NOT NULL;

DO $$ BEGIN
    ALTER TABLE users ADD CONSTRAINT users_username_format_check
        CHECK (username IS NULL OR username ~ '^[A-Za-z][A-Za-z0-9]{5,18}$');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ---------------------------------------------------------------------------
-- security_profiles: the IT 107 registration record.
-- ID Number is the primary key of this table (handout section 4.4). The
-- TaskChain users table keeps its UUID primary key because every task and
-- audit row references it; the 1:1 profile is the registration identity.
-- contact_number_enc is AES-256-GCM ciphertext (nonce || ciphertext).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_profiles (
    id_number VARCHAR(9) PRIMARY KEY,
    user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    first_name VARCHAR(23) NOT NULL,
    middle_name VARCHAR(23),
    family_name VARCHAR(23) NOT NULL,
    name_extension VARCHAR(10),
    birthdate DATE NOT NULL,
    purok_street VARCHAR(50) NOT NULL,
    barangay VARCHAR(50) NOT NULL,
    municipality VARCHAR(50) NOT NULL,
    province VARCHAR(50) NOT NULL,
    country VARCHAR(50) NOT NULL DEFAULT 'Philippines',
    zip_code CHAR(4) NOT NULL,
    office_unit VARCHAR(40) NOT NULL,
    contact_number_enc BYTEA NOT NULL,
    date_of_appointment DATE NOT NULL,
    position_designation VARCHAR(50) NOT NULL,
    privacy_consent_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT security_profiles_id_format CHECK (id_number ~ '^\d{4}-\d{4}$'),
    CONSTRAINT security_profiles_zip_format CHECK (zip_code ~ '^\d{4}$')
);
CREATE INDEX IF NOT EXISTS idx_security_profiles_user ON security_profiles(user_id);

-- ---------------------------------------------------------------------------
-- security_answers: the three seeded questions, hashed like passwords.
-- Answers are lowercased before bcrypt, so "Bantay" and "bantay" match.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_answers (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    question_no SMALLINT NOT NULL,
    answer_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, question_no),
    CONSTRAINT security_answers_question_check CHECK (question_no BETWEEN 1 AND 8)
);

-- ---------------------------------------------------------------------------
-- otp_codes: registration, login and reset one-time codes.
-- The code is hashed; the purpose and expiry are stored so a register code
-- can never be replayed as a login code.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS otp_codes (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose VARCHAR(20) NOT NULL,
    code_hash TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    attempts SMALLINT NOT NULL DEFAULT 0,
    consumed_at TIMESTAMPTZ,
    ip_address INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT otp_purpose_check CHECK (purpose IN ('register', 'login', 'reset'))
);
CREATE INDEX IF NOT EXISTS idx_otp_user_purpose_time ON otp_codes(user_id, purpose, created_at DESC);

-- ---------------------------------------------------------------------------
-- password_history: hashes of recent passwords (protection 7).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS password_history (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_password_history_user ON password_history(user_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- ip_blocks: persistent IP blocking (protection 5). The in-process throttle
-- in app/utils.py is fast but disappears on restart; this table is the
-- authoritative record used by login and Forgot Password.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ip_blocks (
    ip_address INET PRIMARY KEY,
    blocked_until TIMESTAMPTZ NOT NULL,
    reason VARCHAR(255) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ip_blocks_until ON ip_blocks(blocked_until);

-- ---------------------------------------------------------------------------
-- activity_log: every security event (handout section 13.4).
-- Columns match the handout: id, event_type, username_typed, user_id,
-- ip_address, user_agent, details, created_at.
-- Append-only, enforced by PostgreSQL just like audit_logs.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS activity_log (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(60) NOT NULL,
    username_typed TEXT,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    ip_address INET,
    user_agent TEXT,
    details TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_activity_log_time ON activity_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_log_type_time ON activity_log(event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_log_ip_time ON activity_log(ip_address, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_log_user_time ON activity_log(user_id, created_at DESC);

CREATE OR REPLACE FUNCTION forbid_ledger_change() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION '% on % is not allowed: this table is append-only', TG_OP, TG_TABLE_NAME
        USING ERRCODE = 'integrity_constraint_violation';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_activity_log_append_only ON activity_log;
CREATE TRIGGER trg_activity_log_append_only
    BEFORE UPDATE OR DELETE ON activity_log
    FOR EACH ROW EXECUTE FUNCTION forbid_ledger_change();

-- ---------------------------------------------------------------------------
-- security_flags: findings written by scripts/monitor.py.
-- The unique key stops the same pattern and target being flagged twice a day.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_flags (
    id BIGSERIAL PRIMARY KEY,
    pattern VARCHAR(60) NOT NULL,
    target TEXT NOT NULL,
    severity VARCHAR(10) NOT NULL,
    details TEXT NOT NULL DEFAULT '',
    flag_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT security_flags_severity_check CHECK (severity IN ('HIGH', 'MED', 'LOW')),
    CONSTRAINT security_flags_unique_daily UNIQUE (pattern, target, flag_date)
);
CREATE INDEX IF NOT EXISTS idx_security_flags_date ON security_flags(flag_date DESC, created_at DESC);

-- ---------------------------------------------------------------------------
-- password_reset_tokens: one-time proof that steps 1-5 of Forgot Password
-- were completed. Only a SHA-256 hash is stored, so a database reader cannot
-- turn it into a working reset link.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    ip_address INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_reset_tokens_user ON password_reset_tokens(user_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- Existing accounts keep username NULL and sign in with their email. New
-- registrations always get a unique username, so no backfill is attempted:
-- two accounts may share the same email local part on different domains, and
-- a blind backfill would violate the unique index.
-- ---------------------------------------------------------------------------
