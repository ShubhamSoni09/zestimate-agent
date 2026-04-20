"""Optional Apify Actor backend (paid Apify runs; may improve reliability vs raw scraping)."""

from __future__ import annotations

import json
import os
import re
import threading
from typing import Any
from urllib.parse import quote

from .models import ZestimateResult

# Default Apify Actor: accepts `scrape_type` + `multiple_input_box`.
DEFAULT_APIFY_ACTOR_ID = "HGPHGu8INtQpCeF3x"

_apify_client_lock = threading.Lock()
_apify_clients: dict[str, Any] = {}


def _get_apify_client(token: str) -> Any:
    """Reuse one client per token (avoids TLS + client setup on every request)."""
    with _apify_client_lock:
        if token not in _apify_clients:
            from apify_client import ApifyClient

            _apify_clients[token] = ApifyClient(token)
        return _apify_clients[token]


def _digits_to_int(value: str) -> int | None:
    digits = re.sub(r"[^\d]", "", value)
    if not digits:
        return None
    return int(digits)


def _walk_zestimate(node: Any) -> int | None:
    if isinstance(node, dict):
        for key, val in node.items():
            lk = str(key).lower()
            if lk in (
                "zestimate",
                "priceestimate",
                "estimatedvalue",
                "zmiddleestimate",
                "rentzestimate",
            ):
                if isinstance(val, (int, float)):
                    return int(val)
                if isinstance(val, str):
                    n = _digits_to_int(val)
                    if n is not None:
                        return n
            found = _walk_zestimate(val)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _walk_zestimate(item)
            if found is not None:
                return found
    return None


def _walk_property_url(node: Any) -> str | None:
    if isinstance(node, dict):
        for key in ("url", "propertyUrl", "propertyURL", "listingUrl", "link", "href"):
            if key in node and isinstance(node[key], str) and "zillow.com" in node[key]:
                return node[key]
        for val in node.values():
            found = _walk_property_url(val)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _walk_property_url(item)
            if found:
                return found
    return None


def _property_page_from_row(row: dict) -> str | None:
    """Absolute homedetails URL from Zillow hdpUrl path."""
    hdp = row.get("hdpUrl")
    if isinstance(hdp, str) and "/homedetails/" in hdp:
        if hdp.startswith("http"):
            return hdp
        if hdp.startswith("/"):
            return f"https://www.zillow.com{hdp}"
    return None


# Do not descend into these keys when searching for a nested `zestimate` (avoid neighbor comps).
_SKIP_ZESTIMATE_BRANCH_KEYS = frozenset(
    {
        "nearbyhomes",
        "compscarouselpropertyphotos",
        "schools",
        "nearbycities",
        "nearbyneighborhoods",
        "nearbyzipcodes",
        "taxhistory",
        "pricehistory",
        "pals",
        "listedby",
        "comps",
    }
)


def _coerce_zestimate_cell(val: Any) -> int | str:
    """Map JSON `zestimate` cell to int or the string 'not available' (null / unparseable)."""
    if val is None:
        return "not available"
    if isinstance(val, bool):
        return "not available"
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str):
        n = _digits_to_int(val)
        if n is None:
            return "not available"
        return n
    return "not available"


def _walk_zestimate_field_only(node: Any) -> int | str | None:
    """DFS for JSON keys named exactly `zestimate` (case-insensitive), skipping large list branches."""
    if isinstance(node, dict):
        for k, v in node.items():
            lk = str(k).lower()
            if lk == "zestimate":
                return _coerce_zestimate_cell(v)
            if lk in _SKIP_ZESTIMATE_BRANCH_KEYS:
                continue
            inner = _walk_zestimate_field_only(v)
            if inner is not None:
                return inner
    elif isinstance(node, list):
        for item in node:
            inner = _walk_zestimate_field_only(item)
            if inner is not None:
                return inner
    return None


def _resolve_zestimate_strict(primary: dict[str, Any]) -> int | str:
    """Use only the Zillow `zestimate` field (never price/tax fallbacks)."""
    if "zestimate" in primary:
        return _coerce_zestimate_cell(primary["zestimate"])
    prop = primary.get("property")
    if isinstance(prop, dict) and "zestimate" in prop:
        return _coerce_zestimate_cell(prop["zestimate"])
    nested = _walk_zestimate_field_only(primary)
    if nested is not None:
        return nested
    return "not available"


def _resolve_zestimate_from_items(items: list[dict[str, Any]]) -> int | str:
    """Prefer any numeric zestimate in returned rows; else return 'not available'."""
    fallback: int | str = "not available"
    for row in items:
        z = _resolve_zestimate_strict(row)
        if isinstance(z, int):
            return z
        # Keep the first explicit non-numeric result only as a fallback.
        if fallback == "not available" and z != "not available":
            fallback = z
    return fallback


def _walk_homedetails_url(node: Any) -> str | None:
    """First zillow.com/homedetails/ URL found in nested strings."""
    if isinstance(node, dict):
        for val in node.values():
            if isinstance(val, str) and "zillow.com" in val.lower() and "/homedetails/" in val.lower():
                return val
            found = _walk_homedetails_url(val)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _walk_homedetails_url(item)
            if found:
                return found
    return None


def _zillow_search_url(address: str) -> str:
    """Path-style encoding: spaces as %20 (Zillow is picky vs + from quote_plus)."""
    slug = quote(address.strip(), safe="")
    return f"https://www.zillow.com/homes/{slug}_rb/"


def _hgph_input_variants(clean: str) -> list[str]:
    """Input variants for HGPH actor; helps when unit formatting affects matching."""
    variants: list[str] = [clean]
    # "Unit 1507" -> "#1507"
    v_hash = re.sub(r"\bunit\s+(\w+)\b", r"#\1", clean, flags=re.IGNORECASE)
    if v_hash != clean:
        variants.append(v_hash)
    # "#1507" -> "Unit 1507"
    v_unit = re.sub(r"#\s*([A-Za-z0-9-]+)\b", r"Unit \1", clean)
    if v_unit != clean and v_unit not in variants:
        variants.append(v_unit)
    return variants


def _is_maxcopell_zillow_search_scraper(actor_id: str) -> bool:
    return "maxcopell/zillow-scraper" in actor_id.strip().lower()


def _is_hgph_actor(actor_id: str) -> bool:
    """Apify store actor that accepts scrape_type + multiple_input_box."""
    return "hgphgu8intqpcef3x" in actor_id.strip().lower()


def _is_enk9_zillow_actor(actor_id: str) -> bool:
    """Actor ENK9p4RZHg0iVso52 — startUrls, addresses[], propertyStatus, extractBuildingUnits, optional dataset id."""
    return "enk9p4rzhg0ivso52" in actor_id.strip().lower()


def _synthetic_map_url_enabled() -> bool:
    """Build a map-search URL for typed addresses (maxcopell); set APIFY_SYNTHETIC_SEARCH_URL=0 to disable."""
    v = os.getenv("APIFY_SYNTHETIC_SEARCH_URL", "1").strip().lower()
    if not v:
        return True
    return v not in ("0", "false", "no", "off")


def _maxcopell_map_search_url_from_users_term(users_search_term: str) -> str:
    """Zillow for_sale URL with searchQueryState so maxcopell accepts plain street input."""
    term = users_search_term.strip()
    state: dict[str, Any] = {
        "isMapVisible": True,
        "isListVisible": True,
        "pagination": {},
        "mapBounds": {
            "west": -125.0,
            "east": -65.0,
            "south": 24.0,
            "north": 50.0,
        },
        "mapZoom": 4,
        "filterState": {"sort": {"value": "globalrelevanceex"}},
        "usersSearchTerm": term,
    }
    raw = json.dumps(state, separators=(",", ":"))
    enc = quote(raw, safe="")
    return f"https://www.zillow.com/homes/for_sale/?searchQueryState={enc}"


def _dataset_item_limit() -> int | None:
    """Cap rows read from the default dataset (large runs = many HTTP round-trips). 0 or unset = no cap."""
    raw = os.getenv("APIFY_DATASET_ITEM_LIMIT", "120").strip().lower()
    if raw in ("", "0", "all", "none", "unlimited"):
        return None
    try:
        n = int(raw)
        return n if n > 0 else None
    except ValueError:
        return 120


def _dataset_items(client: Any, dataset_id: str) -> list[dict]:
    items: list[dict] = []
    lim = _dataset_item_limit()
    kwargs: dict[str, Any] = {}
    if lim is not None:
        kwargs["limit"] = lim
    for item in client.dataset(dataset_id).iterate_items(**kwargs):
        if isinstance(item, dict):
            items.append(item)
    return items


def _apify_actor_call_kwargs() -> dict[str, Any]:
    """Optional Apify client .call() limits (see Apify Python client docs)."""
    out: dict[str, Any] = {}
    wait = os.getenv("APIFY_WAIT_SECS", "").strip()
    if wait.isdigit():
        out["wait_secs"] = int(wait)
    tout = os.getenv("APIFY_ACTOR_TIMEOUT_SECS", "").strip()
    if tout.isdigit():
        out["timeout_secs"] = int(tout)
    return out


def _run_actor_and_collect(
    client: Any,
    actor_id: str,
    run_input: dict[str, Any],
) -> tuple[dict[str, Any], list[dict]]:
    run = client.actor(actor_id).call(run_input=run_input, **_apify_actor_call_kwargs())
    dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        rid = run.get("id", "?")
        raise ValueError(f"Apify run returned no defaultDatasetId (run id: {rid}).")
    items = _dataset_items(client, dataset_id)
    return run, items


def fetch_zestimate_apify(address: str) -> ZestimateResult:
    """Run configured Apify Actor and map first dataset row to ZestimateResult."""
    token = os.getenv("APIFY_TOKEN", "").strip()
    if not token:
        raise ValueError("APIFY_TOKEN is not set.")

    actor_id = os.getenv("APIFY_ACTOR_ID", DEFAULT_APIFY_ACTOR_ID).strip()
    clean = re.sub(r"\s+", " ", address.strip())
    if not clean:
        raise ValueError("Address cannot be empty.")

    search_url = _zillow_search_url(clean)
    extraction = os.getenv("APIFY_EXTRACTION_METHOD", "PAGINATION_WITH_ZOOM_IN").strip()

    raw_override = os.getenv("APIFY_INPUT_JSON", "").strip()
    if raw_override:
        try:
            run_input = json.loads(raw_override)
        except json.JSONDecodeError as exc:
            raise ValueError("APIFY_INPUT_JSON must be valid JSON.") from exc
        if not isinstance(run_input, dict):
            raise ValueError("APIFY_INPUT_JSON must be a JSON object.")
    elif _is_enk9_zillow_actor(actor_id):
        start_raw = os.getenv("APIFY_START_URLS_JSON", "").strip()
        if start_raw:
            try:
                parsed_urls = json.loads(start_raw)
            except json.JSONDecodeError as exc:
                raise ValueError("APIFY_START_URLS_JSON must be valid JSON.") from exc
            if not isinstance(parsed_urls, list):
                raise ValueError("APIFY_START_URLS_JSON must be a JSON array.")
            start_urls = parsed_urls
        else:
            start_urls = []
        run_input = {
            "startUrls": start_urls,
            "addresses": [clean],
            "propertyStatus": os.getenv("APIFY_PROPERTY_STATUS", "RECENTLY_SOLD").strip()
            or "RECENTLY_SOLD",
            "extractBuildingUnits": os.getenv("APIFY_EXTRACT_BUILDING_UNITS", "all").strip()
            or "all",
        }
        ds_id = os.getenv("APIFY_SEARCH_RESULTS_DATASET_ID", "").strip()
        if ds_id:
            run_input["searchResultsDatasetId"] = ds_id
    elif _is_hgph_actor(actor_id):
        run_input = {
            "scrape_type": "property_addresses",
            "multiple_input_box": clean,
        }
    else:
        literal = os.getenv("APIFY_ZILLOW_SEARCH_URL", "").strip()
        if literal:
            search_url = literal
        elif (
            _is_maxcopell_zillow_search_scraper(actor_id)
            and _synthetic_map_url_enabled()
        ):
            search_url = _maxcopell_map_search_url_from_users_term(clean)
        run_input = {
            "searchUrls": [{"url": search_url}],
            "extractionMethod": extraction,
        }

    if (
        not raw_override
        and _is_maxcopell_zillow_search_scraper(actor_id)
        and "searchquerystate" not in search_url.lower()
    ):
        raise ValueError(
            "Apify actor maxcopell/zillow-scraper only accepts Zillow URLs that include "
            "`?searchQueryState=...`. Plain `/homes/<address>_rb/` links usually return an empty dataset. "
            "Set APIFY_ZILLOW_SEARCH_URL, set APIFY_INPUT_JSON, "
            "or enable automatic map URLs (default on: APIFY_SYNTHETIC_SEARCH_URL=1)."
        )

    try:
        client = _get_apify_client(token)
    except ImportError as exc:
        raise RuntimeError(
            "Apify backend requires the apify-client package. Install with: pip install -e \".[apify]\""
        ) from exc
    run, items = _run_actor_and_collect(client, actor_id, run_input)

    if (
        not items
        and not raw_override
        and _is_maxcopell_zillow_search_scraper(actor_id)
    ):
        alt_input = {
            "startUrls": [{"url": search_url}],
            "extractionMethod": extraction,
        }
        run, items = _run_actor_and_collect(client, actor_id, alt_input)

    if (
        not items
        and not raw_override
        and _is_maxcopell_zillow_search_scraper(actor_id)
    ):
        alt_input2 = {"searchUrls": [{"url": search_url}]}
        run, items = _run_actor_and_collect(client, actor_id, alt_input2)

    if (
        not raw_override
        and _is_hgph_actor(actor_id)
        and not isinstance(_resolve_zestimate_from_items(items), int)
    ):
        scrape_type = "property_addresses"
        for candidate in _hgph_input_variants(clean)[1:]:
            alt_hgph_input = {
                "scrape_type": scrape_type,
                "multiple_input_box": candidate,
            }
            _run2, items2 = _run_actor_and_collect(client, actor_id, alt_hgph_input)
            if items2:
                items = items2
            if isinstance(_resolve_zestimate_from_items(items), int):
                break

    if not items:
        raise ValueError(
            "No listing data came back for that address. "
            "Zillow may not have a match for how it was searched, or the property may not appear in results yet. "
            "Try the full street address, or confirm the home shows on Zillow."
        )

    z = _resolve_zestimate_from_items(items)
    merged: dict[str, Any] = {}
    for it in items:
        merged.update(it)
    primary = items[0]
    property_url = (
        _property_page_from_row(primary)
        or _walk_property_url(primary)
        or _walk_property_url(merged)
        or _walk_homedetails_url(primary)
        or _walk_homedetails_url(merged)
        or search_url
    )

    return ZestimateResult(
        address=clean,
        zestimate=z,
        property_url=property_url,
    )
