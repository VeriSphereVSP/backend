BEGIN;

-- 1) App role (used by services)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT FROM pg_roles WHERE rolname = 'verisphere_app'
  ) THEN
    CREATE ROLE verisphere_app LOGIN PASSWORD 'Nutt1n2s34';
  ELSE
    ALTER ROLE verisphere_app PASSWORD 'Nutt1n2s34';
  END IF;
END
$$;

GRANT CONNECT ON DATABASE verisphere TO verisphere_app;
GRANT USAGE ON SCHEMA public TO verisphere_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO verisphere_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO verisphere_app;
-- 2) Read-only role (nice for pgAdmin)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'verisphere_readonly') THEN
    CREATE ROLE verisphere_readonly LOGIN PASSWORD 'CHANGE_ME_READONLY_PASSWORD';
  END IF;
END $$;

GRANT CONNECT ON DATABASE verisphere TO verisphere_readonly;
GRANT USAGE ON SCHEMA public TO verisphere_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO verisphere_readonly;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO verisphere_readonly;

COMMIT;

