"""Short-TTL in-memory cache for /zestimate (repeat addresses skip Apify/Playwright work)."""

from __future__ import annotations

import hashlib
import os
import threading
import time

from .models import ZestimateResult

_lock = threading.Lock()
_store: dict[str, tuple[float, ZestimateResult]] = {}
_MAX_ENTRIES = 512


def _ttl_seconds() -> float:
    raw = os.getenv("ZESTIMATE_CACHE_TTL_SECS", "300").strip().lower()
    if raw in ("", "0", "false", "no", "off"):
        return 0.0
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 300.0


def _apify_config_fingerprint() -> str:
    """So cache misses when Apify inputs that change results are edited."""
    parts = "".join(
        os.getenv(k, "")
        for k in (
            "APIFY_ACTOR_ID",
            "APIFY_INPUT_JSON",
            "APIFY_START_URLS_JSON",
            "APIFY_ZILLOW_SEARCH_URL",
            "APIFY_PROPERTY_STATUS",
            "APIFY_EXTRACT_BUILDING_UNITS",
            "APIFY_EXTRACTION_METHOD",
            "APIFY_SEARCH_RESULTS_DATASET_ID",
            "APIFY_SCRAPE_TYPE",
            "APIFY_DATASET_ITEM_LIMIT",
        )
    )
    return hashlib.sha256(parts.encode("utf-8", errors="replace")).hexdigest()[:20]


def cache_key(address: str) -> str:
    backend = os.getenv("ZILLOW_BACKEND", "playwright").strip().lower()
    if backend == "apify":
        return f"apify:{_apify_config_fingerprint()}:{address}"
    return f"{backend}:{address}"


def get_cached(address: str) -> ZestimateResult | None:
    ttl = _ttl_seconds()
    if ttl <= 0:
        return None
    key = cache_key(address)
    now = time.monotonic()
    with _lock:
        row = _store.get(key)
        if not row:
            return None
        exp, val = row
        if now > exp:
            del _store[key]
            return None
        return val


def set_cached(address: str, val: ZestimateResult) -> None:
    ttl = _ttl_seconds()
    if ttl <= 0:
        return
    key = cache_key(address)
    exp = time.monotonic() + ttl
    with _lock:
        if len(_store) >= _MAX_ENTRIES and key not in _store:
            oldest = min(_store, key=lambda k: _store[k][0])
            del _store[oldest]
        _store[key] = (exp, val)
