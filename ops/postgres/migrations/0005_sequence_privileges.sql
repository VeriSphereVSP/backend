BEGIN;

-- Ensure app role can use BIGSERIAL / IDENTITY sequences
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'verisphere_app') THEN
    -- Existing sequences
    GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO verisphere_app;

    -- Future sequences created by the migration runner role (postgres)
    ALTER DEFAULT PRIVILEGES IN SCHEMA public
      GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO verisphere_app;
  END IF;
END $$;

-- Optional: allow readonly role to inspect sequences (not required for inserts)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'verisphere_readonly') THEN
    GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO verisphere_readonly;

    ALTER DEFAULT PRIVILEGES IN SCHEMA public
      GRANT SELECT ON SEQUENCES TO verisphere_readonly;
  END IF;
END $$;

COMMIT;

