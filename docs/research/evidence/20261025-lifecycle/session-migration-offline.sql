BEGIN;

-- Running upgrade 8a2b4d6f9c1e -> e1a202610250

CREATE TABLE analyzer_sessions (
    id VARCHAR(64) NOT NULL, 
    user_id INTEGER NOT NULL, 
    username VARCHAR NOT NULL, 
    credential_version VARCHAR(64) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    last_seen TIMESTAMP WITH TIME ZONE NOT NULL, 
    revoked_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_analyzer_sessions_user_id ON analyzer_sessions (user_id);

CREATE INDEX ix_analyzer_sessions_expires_at ON analyzer_sessions (expires_at);

CREATE TABLE analyzer_login_windows (
    id VARCHAR(64) NOT NULL, 
    attempts INTEGER NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

UPDATE alembic_version SET version_num='e1a202610250' WHERE alembic_version.version_num = '8a2b4d6f9c1e';

COMMIT;

