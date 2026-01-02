import os

DATABASE_URL = os.getenv("DATABASE_URL")

EMBEDDINGS_PROVIDER = os.getenv("EMBEDDINGS_PROVIDER", "openai").lower()
EMBEDDINGS_MODEL = os.getenv("EMBEDDINGS_MODEL", "text-embedding-3-large")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

LOG_LEVEL = os.getenv("LOG_LEVEL", "info").lower()

# --- Similarity thresholds ---
# cosine similarity ∈ [0, 1]
DUPLICATE_THRESHOLD = float(os.getenv("DUPLICATE_THRESHOLD", "0.95"))
NEAR_DUPLICATE_THRESHOLD = float(os.getenv("NEAR_DUPLICATE_THRESHOLD", "0.85"))

# Defensive ordering
if NEAR_DUPLICATE_THRESHOLD > DUPLICATE_THRESHOLD:
    NEAR_DUPLICATE_THRESHOLD, DUPLICATE_THRESHOLD = (
        DUPLICATE_THRESHOLD,
        NEAR_DUPLICATE_THRESHOLD,
    )

