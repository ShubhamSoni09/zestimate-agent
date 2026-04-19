"""Optional Apify Actor backend (paid Apify runs; may improve reliability vs raw scraping)."""

from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.parse import quote

from .models import ZestimateResult

# Default Apify Actor: startUrls + addresses + propertyStatus (see Apify Input tab).
DEFAULT_APIFY_ACTOR_ID = "ENK9p4RZHg0iVso52"


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


def _best_home_value_int(row: dict) -> tuple[int, str] | None:
    """
    Top-level valuation fields (avoid nearbyHomes / rentZestimate).
    Order: zestimate, price, taxAssessedValue — matches many Zillow JSON rows when zestimate is null.
    """
    for key, label in (
        ("zestimate", "zestimate"),
        ("price", "price"),
        ("taxAssessedValue", "taxAssessedValue"),
    ):
        if key not in row:
            continue
        val = row[key]
        if val is None:
            continue
        if isinstance(val, (int, float)):
            return int(val), label
        if isinstance(val, str):
            n = _digits_to_int(val)
            if n is not None:
                return n, label
    return None


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


def _is_maxcopell_zillow_search_scraper(actor_id: str) -> bool:
    return "maxcopell/zillow-scraper" in actor_id.strip().lower()


def _is_hgph_zpid_actor(actor_id: str) -> bool:
    """Apify store actor that accepts scrape_type + multiple_input_box (address, ZPID, or Zillow URL)."""
    return "hgphgu8intqpcef3x" in actor_id.strip().lower()


def _is_enk9_zillow_actor(actor_id: str) -> bool:
    """Actor ENK9p4RZHg0iVso52 — startUrls, addresses[], propertyStatus, extractBuildingUnits, optional dataset id."""
    return "enk9p4rzhg0ivso52" in actor_id.strip().lower()


def _is_zillow_map_search_url(s: str) -> bool:
    """True if this looks like a browser map-search URL (actor expects searchQueryState)."""
    t = s.strip()
    if not t.lower().startswith("http"):
        return False
    if "zillow.com" not in t.lower():
        return False
    return "searchquerystate" in t.lower()


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


def _dataset_items(client: Any, dataset_id: str) -> list[dict]:
    items: list[dict] = []
    for item in client.dataset(dataset_id).iterate_items():
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
    try:
        from apify_client import ApifyClient
    except ImportError as exc:
        raise RuntimeError(
            "Apify backend requires the apify-client package. Install with: pip install -e \".[apify]\""
        ) from exc

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
    elif _is_hgph_zpid_actor(actor_id):
        scrape_type = os.getenv("APIFY_SCRAPE_TYPE", "zpids").strip() or "zpids"
        run_input = {
            "scrape_type": scrape_type,
            "multiple_input_box": clean,
        }
    else:
        literal = os.getenv("APIFY_ZILLOW_SEARCH_URL", "").strip()
        if literal:
            search_url = literal
        elif _is_zillow_map_search_url(clean):
            search_url = clean
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
            "Set APIFY_ZILLOW_SEARCH_URL, paste a map URL into the address field, set APIFY_INPUT_JSON, "
            "or enable automatic map URLs (default on: APIFY_SYNTHETIC_SEARCH_URL=1)."
        )

    client = ApifyClient(token)
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

    if not items:
        raise ValueError(
            "No listing data came back for that address. "
            "Zillow may not have a match for how it was searched, or the property may not appear in results yet. "
            "Try the full street address, paste the URL from the property's Zillow page, or confirm the home shows on Zillow."
        )

    merged: dict[str, Any] = {}
    for it in items:
        merged.update(it)

    primary = items[0]
    if _is_enk9_zillow_actor(actor_id):
        best = _best_home_value_int(primary)
        if best is not None:
            z, _src = best
        else:
            z = _walk_zestimate(primary)
    else:
        z = _walk_zestimate(merged) or _walk_zestimate(primary)

    if z is None:
        raise ValueError(
            "Zillow did not return a Zestimate or other usable value for this property. "
            "That often happens when the listing has no public estimate, the unit is hard to match, or the address points somewhere Zillow does not cover. "
            "Try the same address on zillow.com, or submit the property's direct Zillow link."
        )

    prop_url = (
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
        property_url=prop_url,
    )
