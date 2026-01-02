import hashlib
import re

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)

def normalize_text(text: str) -> str:
    """
    Normalize text for semantic identity:
    - lowercase
    - strip punctuation
    - collapse whitespace
    """
    text = text.lower()
    text = _PUNCT_RE.sub("", text)   # remove punctuation
    text = " ".join(text.split())   # normalize whitespace
    return text

def content_hash(text: str) -> str:
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

