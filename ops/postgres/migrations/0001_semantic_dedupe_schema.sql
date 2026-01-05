BEGIN;

-- Create app role if missing (DEV OK; PROD later externalize)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'verisphere_app') THEN
    CREATE ROLE verisphere_app LOGIN PASSWORD 'change_me_app';
  END IF;
END $$;

GRANT CONNECT ON DATABASE verisphere TO verisphere_app;

-- Core tables
CREATE TABLE IF NOT EXISTS claim (
  claim_id     BIGSERIAL PRIMARY KEY,
  claim_text   TEXT NOT NULL,
  content_hash TEXT NOT NULL UNIQUE,
  created_tms  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS claim_embedding (
  claim_id        BIGINT PRIMARY KEY REFERENCES claim(claim_id) ON DELETE CASCADE,
  embedding_model TEXT NOT NULL,
  embedding       vector(3072) NOT NULL,
  updated_tms     TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;

