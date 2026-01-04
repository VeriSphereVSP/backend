from __future__ import annotations

import json
from typing import Generator, Optional, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import (
    DATABASE_URL,
    EMBEDDINGS_MODEL,
    DUPLICATE_THRESHOLD,
)


_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not set")
        _engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
    return _engine


def _get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=_get_engine(),
            autoflush=False,
            autocommit=False,
            future=True,
        )
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = _get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def _is_sqlite(db: Session) -> bool:
    return db.bind.dialect.name == "sqlite"


def _serialize_embedding(embedding):
    return json.dumps(embedding)


# -------------------------------------------------------------------
# Claim + embedding
# -------------------------------------------------------------------

def get_or_create_claim_with_embedding(
    db: Session,
    *,
    claim_text: str,
    embedder,
) -> Tuple[int, bool]:

    from app.hashing import content_hash

    h = content_hash(claim_text)

    row = db.execute(
        text("SELECT claim_id FROM claim WHERE content_hash = :h"),
        {"h": h},
    ).fetchone()

    if row:
        return int(row[0]), False

    claim_id = db.execute(
        text("""
            INSERT INTO claim (claim_text, content_hash)
            VALUES (:t, :h)
            RETURNING claim_id
        """),
        {"t": claim_text, "h": h},
    ).scalar_one()

    embedding = embedder.embed(claim_text)
    if not embedding:
        raise RuntimeError("Embedding provider returned empty vector")

    value = _serialize_embedding(embedding) if _is_sqlite(db) else embedding

    db.execute(
        text("""
            INSERT INTO claim_embedding
              (claim_id, embedding_model, embedding)
            VALUES
              (:id, :model, :vec)
        """),
        {"id": claim_id, "model": EMBEDDINGS_MODEL, "vec": value},
    )

    db.commit()
    return claim_id, True


# -------------------------------------------------------------------
# SC / CCS
# -------------------------------------------------------------------

def assign_claim_to_cluster(
    db: Session,
    *,
    claim_id: int,
    similar: list[dict],
) -> dict:
    """
    Assign claim to an existing cluster or create a new one.
    Returns cluster metadata.
    """

    if similar and similar[0]["similarity"] >= DUPLICATE_THRESHOLD:
        canonical_id = similar[0]["claim_id"]

        cluster_id = db.execute(
            text("""
                SELECT cluster_id
                FROM claim_cluster
                WHERE canonical_claim_id = :cid
            """),
            {"cid": canonical_id},
        ).scalar_one()

        db.execute(
            text("""
                INSERT INTO claim_cluster_member
                  (cluster_id, claim_id, similarity)
                VALUES
                  (:cluster, :claim, :sim)
            """),
            {
                "cluster": cluster_id,
                "claim": claim_id,
                "sim": similar[0]["similarity"],
            },
        )

        db.commit()

        return {
            "cluster_id": cluster_id,
            "canonical_claim_id": canonical_id,
            "relationship": "duplicate",
        }

    # Create new cluster
    cluster_id = db.execute(
        text("""
            INSERT INTO claim_cluster (canonical_claim_id)
            VALUES (:cid)
            RETURNING cluster_id
        """),
        {"cid": claim_id},
    ).scalar_one()

    db.execute(
        text("""
            INSERT INTO claim_cluster_member
              (cluster_id, claim_id, similarity)
            VALUES
              (:cluster, :claim, 1.0)
        """),
        {"cluster": cluster_id, "claim": claim_id},
    )

    db.commit()

    return {
        "cluster_id": cluster_id,
        "canonical_claim_id": claim_id,
        "relationship": "canonical",
    }

