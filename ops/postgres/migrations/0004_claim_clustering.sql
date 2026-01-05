BEGIN;

CREATE TABLE IF NOT EXISTS claim_cluster (
  cluster_id        BIGSERIAL PRIMARY KEY,
  canonical_claim_id BIGINT NOT NULL
    REFERENCES claim(claim_id)
    ON DELETE RESTRICT,
  created_tms       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS claim_cluster_member (
  cluster_id BIGINT NOT NULL
    REFERENCES claim_cluster(cluster_id)
    ON DELETE CASCADE,
  claim_id   BIGINT NOT NULL
    REFERENCES claim(claim_id)
    ON DELETE CASCADE,
  similarity FLOAT NOT NULL,
  created_tms TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (cluster_id, claim_id)
);

CREATE INDEX IF NOT EXISTS idx_claim_cluster_member_claim
  ON claim_cluster_member (claim_id);

COMMIT;

