BEGIN;

CREATE INDEX IF NOT EXISTS idx_claim_cluster_member_cluster
  ON claim_cluster_member (cluster_id);

CREATE INDEX IF NOT EXISTS idx_claim_cluster_canonical
  ON claim_cluster (canonical_claim_id);

COMMIT;

