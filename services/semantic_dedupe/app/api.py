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


class CheckDuplicateRequest(BaseModel):
    claim_text: str
    top_k: int = Field(default=5, ge=1, le=50)


def make_embedder():
    if EMBEDDINGS_PROVIDER == "stub":
        return StubEmbeddingProvider()
    if EMBEDDINGS_PROVIDER == "openai":
        return OpenAIEmbeddingProvider()
    raise RuntimeError(f"Invalid EMBEDDINGS_PROVIDER={EMBEDDINGS_PROVIDER}")


embedder = make_embedder()


def decode_embedding(db: Session, value) -> Optional[List[float]]:
    if value is None:
        return None
    if db.bind.dialect.name == "sqlite":
        return json.loads(value)
    if isinstance(value, str):
        v = value.strip()
        if v.startswith("[") and v.endswith("]"):
            return [float(x) for x in v[1:-1].split(",")]
    return list(value)


def topk(db: Session, claim_id: int, query_emb, k: int):
    rows = db.execute(
        text("""
            SELECT c.claim_id, c.claim_text, e.embedding
            FROM claim c
            JOIN claim_embedding e USING (claim_id)
            WHERE c.claim_id != :id
        """),
        {"id": claim_id},
    ).fetchall()

    scored = []
    for cid, text_, emb in rows:
        emb_vec = decode_embedding(db, emb)
        if not emb_vec:
            continue
        sim = cosine_similarity(query_emb, emb_vec)
        scored.append({
            "claim_id": cid,
            "text": text_,
            "similarity": sim,
        })

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:k]


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/claims/check-duplicate")
def check_duplicate(req: CheckDuplicateRequest, db: Session = Depends(get_db)):
    try:
        t0 = time.time()

        claim_id, created = get_or_create_claim_with_embedding(
            db,
            claim_text=req.claim_text,
            embedder=embedder,
        )

        row = db.execute(
            text("SELECT embedding FROM claim_embedding WHERE claim_id = :id"),
            {"id": claim_id},
        ).fetchone()

        if not row:
            raise RuntimeError("Missing embedding")

        query_emb = decode_embedding(db, row[0])
        similar = topk(db, claim_id, query_emb, req.top_k)

        cluster_info = assign_claim_to_cluster(
            db,
            claim_id=claim_id,
            similar=similar,
        )

        max_sim = similar[0]["similarity"] if similar else 0.0

        return {
            "hash": content_hash(req.claim_text),
            "claim_id": claim_id,
            "created": created,
            "embedding_model": EMBEDDINGS_MODEL,
            "provider": EMBEDDINGS_PROVIDER,
            "classification": (
                "duplicate" if max_sim >= DUPLICATE_THRESHOLD
                else "near_duplicate" if max_sim >= NEAR_DUPLICATE_THRESHOLD
                else "new"
            ),
            "cluster": cluster_info,
            "similar": similar,
            "timing_ms": int((time.time() - t0) * 1000),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

