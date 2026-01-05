import json
import time
from typing import Any, Dict, List, Optional, Literal

from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db import (
    get_db,
    get_or_create_claim_with_embedding,
    assign_claim_to_cluster,
    fetch_claim_text,
)
from app.hashing import content_hash
from app.similarity import cosine_similarity
from app.config import (
    EMBEDDINGS_PROVIDER,
    EMBEDDINGS_MODEL,
    DUPLICATE_THRESHOLD,
    NEAR_DUPLICATE_THRESHOLD,
)

from app.embedding.openai_provider import OpenAIEmbeddingProvider
from app.embedding.stub_provider import StubEmbeddingProvider


app = FastAPI(title="VeriSphere Semantic Dedupe")


# ---------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------

class CheckDuplicateRequest(BaseModel):
    claim_text: str
    top_k: int = Field(default=5, ge=1, le=50)


class BatchCheckDuplicateRequest(BaseModel):
    claims: List[str] = Field(min_length=1, max_length=200)
    top_k: int = Field(default=5, ge=1, le=50)


# ---------------------------------------------------------------------
# Embedding provider
# ---------------------------------------------------------------------

def make_embedder():
    if EMBEDDINGS_PROVIDER == "stub":
        return StubEmbeddingProvider()
    if EMBEDDINGS_PROVIDER == "openai":
        return OpenAIEmbeddingProvider()
    raise RuntimeError(f"Invalid EMBEDDINGS_PROVIDER={EMBEDDINGS_PROVIDER}")


try:
    embedder = make_embedder()
except Exception as e:
    raise RuntimeError(f"Embedding provider misconfigured: {e}") from e


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

Classification = Literal["duplicate", "near_duplicate", "new"]


def classify(sim: float) -> Classification:
    if sim >= DUPLICATE_THRESHOLD:
        return "duplicate"
    if sim >= NEAR_DUPLICATE_THRESHOLD:
        return "near_duplicate"
    return "new"


def decode_embedding(db: Session, value) -> Optional[List[float]]:
    """
    Normalize embedding from DB into List[float].

    - SQLite (tests): JSON text
    - Postgres (pgvector): may come back as string "[0.1,0.2,...]"
    """
    if value is None:
        return None

    if db.bind.dialect.name == "sqlite":
        return json.loads(value)

    if isinstance(value, str):
        v = value.strip()
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            if inner == "":
                return []
            return [float(x) for x in inner.split(",") if x.strip()]

    try:
        return list(value)
    except TypeError:
        return None


def pgvector_topk(db: Session, claim_id: int, top_k: int) -> List[Dict[str, Any]]:
    rows = db.execute(
        text(
            """
            WITH q AS (
              SELECT embedding
              FROM claim_embedding
              WHERE claim_id = :claim_id
            )
            SELECT
              c.claim_id,
              c.claim_text,
              (1.0 - (e.embedding <=> q.embedding)) AS similarity
            FROM claim c
            JOIN claim_embedding e USING (claim_id)
            CROSS JOIN q
            WHERE c.claim_id != :claim_id
            ORDER BY (e.embedding <=> q.embedding) ASC
            LIMIT :top_k
            """
        ),
        {"claim_id": claim_id, "top_k": top_k},
    ).fetchall()

    return [
        {"claim_id": int(cid), "text": str(text_), "similarity": float(sim)}
        for cid, text_, sim in rows
    ]


def python_topk(db: Session, claim_id: int, query_emb: List[float], top_k: int) -> List[Dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT c.claim_id, c.claim_text, e.embedding
            FROM claim c
            JOIN claim_embedding e USING (claim_id)
            WHERE c.claim_id != :id
            """
        ),
        {"id": claim_id},
    ).fetchall()

    scored: List[Dict[str, Any]] = []
    for cid, text_, emb in rows:
        emb_vec = decode_embedding(db, emb)
        if not emb_vec:
            continue
        sim = cosine_similarity(query_emb, emb_vec)
        scored.append({"claim_id": int(cid), "text": str(text_), "similarity": float(sim)})

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:top_k]


def compute_one(db: Session, claim_text: str, top_k: int) -> Dict[str, Any]:
    t0 = time.time()

    claim_id, created = get_or_create_claim_with_embedding(
        db,
        claim_text=claim_text,
        embedder=embedder,
    )

    # Similarity search
    if db.bind.dialect.name == "postgresql":
        similar = pgvector_topk(db, claim_id, top_k)
    else:
        row = db.execute(
            text("SELECT embedding FROM claim_embedding WHERE claim_id = :id"),
            {"id": claim_id},
        ).fetchone()
        if not row:
            raise RuntimeError("Missing embedding")
        query_emb = decode_embedding(db, row[0])
        if not query_emb:
            raise RuntimeError("Failed to decode embedding")
        similar = python_topk(db, claim_id, query_emb, top_k)

    max_sim = float(similar[0]["similarity"]) if similar else 0.0
    best_match_id = int(similar[0]["claim_id"]) if similar else None
    classification = classify(max_sim)

    # SC/CCS cluster assignment
    cluster_info = assign_claim_to_cluster(
        db,
        claim_id=claim_id,
        best_match_claim_id=best_match_id,
        best_match_similarity=max_sim,
        join_threshold=NEAR_DUPLICATE_THRESHOLD,
    )

    canonical_claim_id = int(cluster_info["canonical_claim_id"])
    canonical_text = fetch_claim_text(db, canonical_claim_id)

    return {
        "hash": content_hash(claim_text),
        "claim_id": claim_id,
        "created": created,
        "embedding_model": EMBEDDINGS_MODEL,
        "provider": EMBEDDINGS_PROVIDER,

        "classification": classification,
        "max_similarity": max_sim,
        "similar": similar,

        # SC/CCS output
        "cluster_id": int(cluster_info["cluster_id"]),
        "canonical_claim": {
            "claim_id": canonical_claim_id,
            "text": canonical_text,
        },

        "timing_ms": int((time.time() - t0) * 1000),
    }


# ---------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------

@app.get("/health")
def health():
    return {"ok": True}


@app.post("/claims/check-duplicate")
def check_duplicate(req: CheckDuplicateRequest, db: Session = Depends(get_db)):
    try:
        return compute_one(db, req.claim_text, req.top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/claims/check-duplicate-batch")
def check_duplicate_batch(req: BatchCheckDuplicateRequest, db: Session = Depends(get_db)):
    try:
        return {"results": [compute_one(db, claim_text, req.top_k) for claim_text in req.claims]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

