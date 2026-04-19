from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup

NA = "not available"


def _to_int(value: str) -> int | None:
    digits = re.sub(r"[^\d]", "", value)
    if not digits:
        return None
    return int(digits)


def _walk_for_zestimate_key_only(node: Any) -> list[tuple[str, Any]]:
    """Collect (key, value) pairs where key is exactly `zestimate` (case-insensitive)."""
    hits: list[tuple[str, Any]] = []
    if isinstance(node, dict):
        for key, val in node.items():
            if str(key).lower() == "zestimate":
                hits.append((key, val))
            hits.extend(_walk_for_zestimate_key_only(val))
    elif isinstance(node, list):
        for item in node:
            hits.extend(_walk_for_zestimate_key_only(item))
    return hits


def _coerce_zestimate_json_value(val: Any) -> int | str:
    if val is None:
        return NA
    if isinstance(val, bool):
        return NA
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str):
        maybe = _to_int(val)
        if maybe is not None:
            return maybe
        return NA
    return NA


def extract_zestimate(html: str) -> tuple[int | str, str]:
    """
    Read only the `zestimate` JSON field from the page (no price / estimatedValue fallbacks).
    Returns (int, source) or ("not available", reason).
    """
    soup = BeautifulSoup(html, "html.parser")

    # 1) __NEXT_DATA__ (primary source for modern Zillow)
    next_data = soup.find("script", attrs={"id": "__NEXT_DATA__"})
    if next_data and next_data.string:
        try:
            payload = json.loads(next_data.string)
            for key, val in _walk_for_zestimate_key_only(payload):
                out = _coerce_zestimate_json_value(val)
                return out, f"next_data:{key}"
        except json.JSONDecodeError:
            pass

    # 2) JSON-LD — only keys named zestimate
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        content = script.string
        if not content:
            continue
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            continue
        for key, val in _walk_for_zestimate_key_only(payload):
            out = _coerce_zestimate_json_value(val)
            return out, f"jsonld:{key}"

    # 3) Raw HTML: "zestimate": null | number
    m = re.search(
        r'"zestimate"\s*:\s*(null|true|false|\d+|"[^"]*")',
        html,
        flags=re.IGNORECASE,
    )
    if m:
        raw = m.group(1).strip().lower()
        if raw == "null" or raw in ("true", "false"):
            return NA, "raw_html:zestimate_null"
        if raw.isdigit():
            return int(raw), "raw_html:zestimate"
        if raw.startswith('"'):
            inner = raw[1:-1]
            maybe = _to_int(inner)
            if maybe is not None:
                return maybe, "raw_html:zestimate_string"
        return NA, "raw_html:zestimate_unparseable"

    return NA, "no_zestimate_field"
