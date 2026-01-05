from __future__ import annotations

import json
from typing import Generator, Optional, Tuple, Dict, Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import DATABASE_URL, EMBEDDINGS_MODEL


# -------------------------------------------------------------------
# Lazy engine/session creation
# -------------------------------------------------------------------

_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def _get_engine() -> Engine:
    global _engine
    if _engine is not None:
        return _engine

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")

    _engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        future=True,
    )
    return _engine


def _get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is not None:
        return _SessionLocal

    engine = _get_engine()
    _SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        future=True,
    )
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    SessionLocal = _get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _is_sqlite(db: Session) -> bool:
    return db.bind.dialect.name == "sqlite"


def _serialize_embedding(embedding):
    """
    SQLite cannot store vectors; Postgres (pgvector) can.
    """
    return json.dumps(embedding)


# -------------------------------------------------------------------
# Claim persistence
# -------------------------------------------------------------------

def get_or_create_claim_with_embedding(
    db: Session,
    *,
    claim_text: str,
    embedder,
) -> Tuple[int, bool]:
    """
    Returns (claim_id, created)

    created=True iff the embedding was newly computed & stored.
    """

    from app.hashing import content_hash

    h = content_hash(claim_text)

    # 1) Lookup existing claim
    row = db.execute(
        text(
            """
            SELECT claim_id
            FROM claim
            WHERE content_hash = :h
            """
        ),
        {"h": h},
    ).fetchone()

    if row:
        return int(row[0]), False

    # 2) Insert claim
    row = db.execute(
        text(
            """
            INSERT INTO claim (claim_text, content_hash)
            VALUES (:t, :h)
            RETURNING claim_id
            """
        ),
        {"t": claim_text, "h": h},
    ).fetchone()

    if not row:
        raise RuntimeError("Failed to insert claim")

    claim_id = int(row[0])

    # 3) Compute embedding exactly once
    embedding = embedder.embed(claim_text)
    if not embedding:
        raise RuntimeError("Embedding provider returned empty embedding")

    # 4) Store embedding
    value = _serialize_embedding(embedding) if _is_sqlite(db) else embedding

    db.execute(
        text(
            """
            INSERT INTO claim_embedding
              (claim_id, embedding_model, embedding)
            VALUES
              (:id, :model, :vec)
            """
        ),
        {
            "id": claim_id,
            "model": EMBEDDINGS_MODEL,
            "vec": value,
        },
    )

    db.commit()
    return claim_id, True


# -------------------------------------------------------------------
# SC/CCS: Semantic Clustering / Canonical Claim Selection
# -------------------------------------------------------------------

def _get_existing_cluster_id(db: Session, claim_id: int) -> Optional[int]:
    row = db.execute(
        text(
            """
            SELECT cluster_id
            FROM claim_cluster_member
            WHERE claim_id = :claim_id
            """
        ),
        {"claim_id": claim_id},
    ).fetchone()
    return int(row[0]) if row else None


def _get_canonical_claim_id(db: Session, cluster_id: int) -> int:
    row = db.execute(
        text(
            """
            SELECT canonical_claim_id
            FROM claim_cluster
            WHERE cluster_id = :cluster_id
            """
        ),
        {"cluster_id": cluster_id},
    ).fetchone()
    if not row:
        raise RuntimeError(f"claim_cluster missing cluster_id={cluster_id}")
    return int(row[0])


def _ensure_cluster_with_canonical(db: Session, canonical_claim_id: int) -> int:
    """
    Ensure there is a cluster whose canonical is canonical_claim_id.
    Returns cluster_id.
    """
    row = db.execute(
        text(
            """
            SELECT cluster_id
            FROM claim_cluster
            WHERE canonical_claim_id = :cid
            """
        ),
        {"cid": canonical_claim_id},
    ).fetchone()

    if row:
        return int(row[0])

    row = db.execute(
        text(
            """
            INSERT INTO claim_cluster (canonical_claim_id)
            VALUES (:cid)
            RETURNING cluster_id
            """
        ),
        {"cid": canonical_claim_id},
    ).fetchone()

    if not row:
        raise RuntimeError("Failed to create claim_cluster")

    cluster_id = int(row[0])

    # Ensure canonical is a member with similarity=1.0
    db.execute(
        text(
            """
            INSERT INTO claim_cluster_member (cluster_id, claim_id, similarity)
            VALUES (:cluster_id, :claim_id, :sim)
            ON CONFLICT (cluster_id, claim_id) DO NOTHING
            """
        ),
        {"cluster_id": cluster_id, "claim_id": canonical_claim_id, "sim": 1.0},
    )

    return cluster_id


def assign_claim_to_cluster(
    db: Session,
    *,
    claim_id: int,
    best_match_claim_id: Optional[int],
    best_match_similarity: float,
    join_threshold: float,
) -> Dict[str, Any]:
    """
    Assign claim_id to a cluster and return cluster metadata.

    MVP rules:
      - If claim already has a cluster: no-op, return it.
      - If best_match_similarity >= join_threshold:
          - Join best_match_claim_id's cluster if it has one
          - Else create a cluster with canonical=best_match_claim_id
      - Else:
          - Create cluster with canonical=claim_id

    Canonical selection (CCS) is stable in MVP: we do not re-elect canonicals.
    """

    existing_cluster = _get_existing_cluster_id(db, claim_id)
    if existing_cluster is not None:
        canonical_id = _get_canonical_claim_id(db, existing_cluster)
        return {
            "cluster_id": existing_cluster,
            "canonical_claim_id": canonical_id,
            "assigned": False,
        }

    # Determine target cluster
    if best_match_claim_id is not None and best_match_similarity >= join_threshold:
        bm_cluster = _get_existing_cluster_id(db, best_match_claim_id)
        if bm_cluster is not None:
            cluster_id = bm_cluster
        else:
            cluster_id = _ensure_cluster_with_canonical(db, best_match_claim_id)
    else:
        cluster_id = _ensure_cluster_with_canonical(db, claim_id)

    canonical_id = _get_canonical_claim_id(db, cluster_id)

    # Store membership similarity.
    # For canonical itself => 1.0, otherwise store best-match similarity.
    sim = 1.0 if claim_id == canonical_id else float(best_match_similarity)

    db.execute(
        text(
            """
            INSERT INTO claim_cluster_member (cluster_id, claim_id, similarity)
            VALUES (:cluster_id, :claim_id, :sim)
            ON CONFLICT (cluster_id, claim_id) DO NOTHING
            """
        ),
        {"cluster_id": cluster_id, "claim_id": claim_id, "sim": sim},
    )

    db.commit()

    return {
        "cluster_id": cluster_id,
        "canonical_claim_id": canonical_id,
        "assigned": True,
    }


def fetch_claim_text(db: Session, claim_id: int) -> Optional[str]:
    row = db.execute(
        text("SELECT claim_text FROM claim WHERE claim_id = :id"),
        {"id": claim_id},
    ).fetchone()
    return str(row[0]) if row else None

