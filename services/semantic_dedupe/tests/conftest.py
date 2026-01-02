import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.embedding.stub_provider import StubEmbeddingProvider


@pytest.fixture()
def embedder():
    return StubEmbeddingProvider()


@pytest.fixture()
def db_session():
    """
    Use an in-memory SQLite DB for unit tests.
    We create minimal tables matching the service schema.
    """
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with engine.begin() as conn:
        # SQLite doesn't have pgvector; store embedding as TEXT.
        conn.execute(text("""
            CREATE TABLE claim (
              claim_id      INTEGER PRIMARY KEY AUTOINCREMENT,
              claim_text    TEXT NOT NULL,
              content_hash  TEXT NOT NULL UNIQUE,
              created_tms   TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """))

        conn.execute(text("""
            CREATE TABLE claim_embedding (
              claim_id         INTEGER PRIMARY KEY,
              embedding_model  TEXT NOT NULL,
              embedding        TEXT NOT NULL,
              updated_tms      TEXT NOT NULL DEFAULT (datetime('now')),
              FOREIGN KEY (claim_id) REFERENCES claim(claim_id) ON DELETE CASCADE
            );
        """))

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

