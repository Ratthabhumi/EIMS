-- EIMS step 1/2 — role topology (run as database owner or superuser).
--
-- Idempotent and *self-correcting*: it tightens an existing role as well as
-- creating a missing one. Run before migrations.
--
--   psql "$OWNER_URL" -f deploy/sql/01_roles.sql
--
-- Override names without editing:
--   SET eims.mig_role = 'eims_migrator';
--   SET eims.runtime_role = 'eims_runtime';
--
-- Passwords are deliberately NOT set here: assign them from the secret store
-- (`ALTER ROLE ... PASSWORD` through your secret manager) so they never appear
-- in a script, shell history or the process list.

-- Extensions the migrations require, created while a superuser is available.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

DO $$
DECLARE
    mig text := COALESCE(current_setting('eims.mig_role', true), 'eims_migrator');
    rt  text := COALESCE(current_setting('eims.runtime_role', true), 'eims_runtime');
    db  text := current_database();
    rec record;
BEGIN
    IF mig = rt THEN
        RAISE EXCEPTION 'migration and runtime roles must differ (% = %)', mig, rt;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = mig) THEN
        EXECUTE format('CREATE ROLE %I LOGIN', mig);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = rt) THEN
        EXECUTE format('CREATE ROLE %I LOGIN', rt);
    END IF;

    -- Always enforce the posture, even for a pre-existing role.
    EXECUTE format(
        'ALTER ROLE %I NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS', mig);
    EXECUTE format(
        'ALTER ROLE %I NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS', rt);

    -- The runtime must hold no role membership at all: no SET ROLE to an owner
    -- and no inherited privileges.
    FOR rec IN
        SELECT r.rolname
        FROM pg_auth_members m
        JOIN pg_roles r ON r.oid = m.roleid
        WHERE m.member = rt::regrole
    LOOP
        EXECUTE format('REVOKE %I FROM %I', rec.rolname, rt);
    END LOOP;
    EXECUTE format('REVOKE %I FROM %I', mig, rt);

    EXECUTE format('REVOKE ALL ON DATABASE %I FROM PUBLIC', db);
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO %I', db, mig);
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO %I', db, rt);

    -- The migration role creates the schema objects, so it needs CREATE; the
    -- runtime must never have it (it could then own/alter protected objects).
    EXECUTE format('GRANT USAGE, CREATE ON SCHEMA public TO %I', mig);
    EXECUTE format('GRANT USAGE ON SCHEMA public TO %I', rt);
    EXECUTE format('REVOKE CREATE ON SCHEMA public FROM %I', rt);
END
$$;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
