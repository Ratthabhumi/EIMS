-- EIMS step 2/2 — runtime grants (run AFTER migrations, as owner/superuser).
--
--   psql "$OWNER_URL" -f deploy/sql/02_runtime_grants.sql
--
-- The runtime role must be able to run the whole application, so it receives
-- SELECT/INSERT/UPDATE/DELETE on application tables. Least privilege is applied
-- where the blast radius is: the append-only verification history, the audit
-- journal, incident deletion, and every DDL/trigger capability are removed.
-- The DB guards (owned by the migration role) enforce the invariants on top.
--
-- RUN THIS AFTER EVERY MIGRATION. It grants on the tables that exist now and
-- sets default privileges for future ones; a later migration that recreates a
-- protected table would otherwise regain UPDATE/DELETE for the runtime role.
--
-- Override with:
--   SET eims.mig_role='...'; SET eims.runtime_role='...'; SET eims.schema='public';

DO $$
DECLARE
    mig text := COALESCE(current_setting('eims.mig_role', true), 'eims_migrator');
    rt  text := COALESCE(current_setting('eims.runtime_role', true), 'eims_runtime');
    sch text := COALESCE(current_setting('eims.schema', true), 'public');
    tbl text;
BEGIN
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO %I', sch, rt);
    EXECUTE format('GRANT USAGE ON ALL SEQUENCES IN SCHEMA %I TO %I', sch, rt);

    -- Protected table-by-table overrides.
    FOREACH tbl IN ARRAY ARRAY['incident_verification', 'audit_logs'] LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = sch AND table_name = tbl
        ) THEN
            EXECUTE format('REVOKE UPDATE, DELETE, TRUNCATE ON %I.%I FROM %I', sch, tbl, rt);
        END IF;
    END LOOP;
    FOREACH tbl IN ARRAY ARRAY['incidents', 'incident_evidence'] LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = sch AND table_name = tbl
        ) THEN
            EXECUTE format('REVOKE DELETE, TRUNCATE ON %I.%I FROM %I', sch, tbl, rt);
        END IF;
    END LOOP;

    -- Evidence rows are immutable after attachment: the service never updates
    -- them, and a rewritten added_by/created_at would defeat verification.
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = sch AND table_name = 'incident_evidence'
    ) THEN
        EXECUTE format('REVOKE UPDATE ON %I.incident_evidence FROM %I', sch, rt);
    END IF;

    -- Migration bookkeeping is not application data. Schema-version readiness is
    -- checked by the deploy pipeline (with the migration credential), not by the
    -- runtime role.
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = sch AND table_name = 'alembic_version'
    ) THEN
        EXECUTE format('REVOKE ALL ON %I.alembic_version FROM %I', sch, rt);
    END IF;

    EXECUTE format('REVOKE CREATE ON SCHEMA %I FROM %I', sch, rt);
    EXECUTE format('REVOKE CREATE ON SCHEMA %I FROM PUBLIC', sch);

    EXECUTE format(
        'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I '
        'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %I', mig, sch, rt);
    EXECUTE format(
        'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I '
        'GRANT USAGE ON SEQUENCES TO %I', mig, sch, rt);
END
$$;

-- Fail loudly if the topology is wrong: a runtime that owns relations or holds
-- any role membership can defeat the guards, and the deploy must not proceed.
DO $$
DECLARE
    rt text := COALESCE(current_setting('eims.runtime_role', true), 'eims_runtime');
    sch text := COALESCE(current_setting('eims.schema', true), 'public');
    memberships int;
    owned int;
    posture record;
BEGIN
    SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolinherit
      INTO posture FROM pg_roles WHERE rolname = rt;
    IF posture.rolsuper OR posture.rolbypassrls OR posture.rolcreatedb
       OR posture.rolcreaterole OR posture.rolinherit THEN
        RAISE EXCEPTION 'runtime role % posture is not least-privilege: %', rt, posture;
    END IF;

    SELECT count(*) INTO memberships FROM pg_auth_members WHERE member = rt::regrole;
    IF memberships <> 0 THEN
        RAISE EXCEPTION 'runtime role % holds % role membership(s)', rt, memberships;
    END IF;

    SELECT count(*) INTO owned
      FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = sch AND c.relowner = rt::regrole;
    IF owned <> 0 THEN
        RAISE EXCEPTION 'runtime role % owns % relation(s) in schema %', rt, owned, sch;
    END IF;
END
$$;

-- Post-run verification (must all hold):
--   SELECT rolname, rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolinherit
--     FROM pg_roles WHERE rolname = current_user;
--   SELECT pg_get_userbyid(relowner) FROM pg_class WHERE relname = 'incidents';
--   SELECT pg_has_role(current_user, '<migration_role>', 'MEMBER');  -- false
