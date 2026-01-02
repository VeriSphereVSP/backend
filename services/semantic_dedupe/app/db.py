from __future__ import annotations

import json
from typing import Generator, Optional, Tuple

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
# Persistence
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

    claim_id = int(row[0])

    # 3) Compute embedding exactly once
    embedding = embedder.embed(claim_text)

    if not embedding:
        raise RuntimeError("Embedding provider returned empty embedding")

    # 4) Store embedding
    value = (
        _serialize_embedding(embedding)
        if _is_sqlite(db)
        else embedding
    )

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

