from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup


USD_VALUE_RE = re.compile(r"\$?\s*([1-9]\d{0,2}(?:,\d{3})+)")


def _to_int(value: str) -> int | None:
    digits = re.sub(r"[^\d]", "", value)
    if not digits:
        return None
    return int(digits)


def _walk_for_key(node: Any, keys: set[str]) -> list[tuple[str, Any]]:
    hits: list[tuple[str, Any]] = []
    if isinstance(node, dict):
        for key, val in node.items():
            if key.lower() in keys:
                hits.append((key, val))
            hits.extend(_walk_for_key(val, keys))
    elif isinstance(node, list):
        for item in node:
            hits.extend(_walk_for_key(item, keys))
    return hits


def extract_zestimate(html: str) -> tuple[int, str]:
    soup = BeautifulSoup(html, "html.parser")

    # 1) Prefer JSON-LD structured data when available.
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        content = script.string
        if not content:
            continue
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            continue
        for key, val in _walk_for_key(payload, {"zestimate", "estimatedvalue", "estimate"}):
            if isinstance(val, (int, float)):
                return int(val), f"jsonld:{key}"
            if isinstance(val, str):
                maybe = _to_int(val)
                if maybe:
                    return maybe, f"jsonld:{key}"

    # 2) Next.js hydration payload is generally closest to visible UI value.
    next_data = soup.find("script", attrs={"id": "__NEXT_DATA__"})
    if next_data and next_data.string:
        try:
            payload = json.loads(next_data.string)
            for key, val in _walk_for_key(payload, {"zestimate", "priceestimate", "estimatedvalue"}):
                if isinstance(val, (int, float)):
                    return int(val), f"next_data:{key}"
                if isinstance(val, str):
                    maybe = _to_int(val)
                    if maybe:
                        return maybe, f"next_data:{key}"
        except json.JSONDecodeError:
            pass

    # 3) Raw HTML JSON snippets (escaped or inline state blobs).
    raw_patterns = [
        r'"zestimate"\s*:\s*"?\$?([0-9,]+)"?',
        r'"estimatedValue"\s*:\s*"?\$?([0-9,]+)"?',
        r'"priceEstimate"\s*:\s*"?\$?([0-9,]+)"?',
    ]
    for pattern in raw_patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if not match:
            continue
        maybe = _to_int(match.group(1))
        if maybe:
            return maybe, "raw_html_json"

    # 4) Fallback: find currency values near Zestimate label.
    text = soup.get_text("\n", strip=True)
    marker_patterns = [
        r"zestimate[^$\n]{0,80}(\$[0-9,]+)",
        r"zillow estimate[^$\n]{0,80}(\$[0-9,]+)",
    ]
    for pattern in marker_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        maybe = _to_int(match.group(1))
        if maybe:
            return maybe, "text_near_label"

    # 5) Last resort: take the first high-confidence money-like value.
    for match in USD_VALUE_RE.finditer(text):
        maybe = _to_int(match.group(1))
        if maybe:
            return maybe, "money_regex_fallback"

    raise ValueError(
        "We could not read a Zestimate from this Zillow page. "
        "The listing may not show one, or the page did not load the usual data. "
        "Try another address format or the property's direct Zillow URL."
    )
