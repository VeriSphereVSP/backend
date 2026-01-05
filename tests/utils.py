from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional, Tuple

import requests


DEFAULT_TIMEOUT = float(os.getenv("VSB_TEST_HTTP_TIMEOUT_SECS", "8.0"))
RETRY_SECS = float(os.getenv("VSB_TEST_RETRY_SECS", "0.5"))
RETRY_MAX = int(os.getenv("VSB_TEST_RETRY_MAX", "20"))


class HttpError(RuntimeError):
    pass


def _join(base: str, path: str) -> str:
    if not base:
        raise ValueError("base url is empty")
    if not path.startswith("/"):
        path = "/" + path
    return base.rstrip("/") + path


def http_get_json(url: str, *, timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    r = requests.get(url, timeout=timeout)
    if r.status_code >= 400:
        raise HttpError(f"GET {url} -> {r.status_code}: {r.text[:300]}")
    return r.json()


def http_post_json(url: str, payload: Dict[str, Any], *, timeout: float = DEFAULT_TIMEOUT) -> Tuple[int, Any, str]:
    r = requests.post(url, json=payload, timeout=timeout)
    text = r.text or ""
    try:
        body = r.json()
    except Exception:
        body = None
    return r.status_code, body, text


def wait_for_health(base_url: str, health_path: str = "/health") -> None:
    url = _join(base_url, health_path)
    last_err: Optional[str] = None
    for _ in range(RETRY_MAX):
        try:
            r = requests.get(url, timeout=DEFAULT_TIMEOUT)
            if r.status_code < 400:
                # Allow either {"ok": true} or similar.
                return
            last_err = f"{r.status_code}: {r.text[:200]}"
        except Exception as e:
            last_err = str(e)
        time.sleep(RETRY_SECS)
    raise HttpError(f"Service not healthy at {url}. Last error: {last_err}")


def assert_stable_4xx_or_200(status_code: int) -> None:
    """
    For "weird" inputs we accept either:
      - 200 with safe empty/flagged output, OR
      - 4xx with a clean error (never 5xx).
    """
    assert status_code < 500, f"Unexpected 5xx: {status_code}"
    assert status_code == 200 or 400 <= status_code < 500, f"Unexpected status: {status_code}"
