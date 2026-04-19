from __future__ import annotations

from typing import Any

import pytest

from zestimate_agent.apify_backend import fetch_zestimate_apify


def test_enk9_actor_builds_default_input(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, Any]] = []

    def fake_run(
        _client: Any,
        _actor_id: str,
        run_input: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict]]:
        captured.append(run_input)
        row = {
            "zestimate": None,
            "price": 64706,
            "taxAssessedValue": 64706,
            "hdpUrl": "/homedetails/32-Winspear-Ave-Buffalo-NY-14214/132916029_zpid/",
        }
        return ({"id": "1", "defaultDatasetId": "ds1"}, [row])

    monkeypatch.setenv("APIFY_TOKEN", "dummy")
    monkeypatch.setenv("APIFY_ACTOR_ID", "ENK9p4RZHg0iVso52")
    monkeypatch.delenv("APIFY_INPUT_JSON", raising=False)
    monkeypatch.delenv("APIFY_START_URLS_JSON", raising=False)
    monkeypatch.delenv("APIFY_SEARCH_RESULTS_DATASET_ID", raising=False)
    monkeypatch.setattr("zestimate_agent.apify_backend._run_actor_and_collect", fake_run)

    result = fetch_zestimate_apify("32 Winspear Ave, Buffalo, NY 14214")
    assert result.zestimate == 64706
    assert result.property_url == (
        "https://www.zillow.com/homedetails/32-Winspear-Ave-Buffalo-NY-14214/132916029_zpid/"
    )
    inp = captured[0]
    assert inp["addresses"] == ["32 Winspear Ave, Buffalo, NY 14214"]
    assert inp["propertyStatus"] == "RECENTLY_SOLD"
    assert inp["extractBuildingUnits"] == "all"
    assert inp["startUrls"] == []


def test_enk9_prefers_zestimate_over_price(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(
        _client: Any,
        _actor_id: str,
        _run_input: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict]]:
        return (
            {"id": "1", "defaultDatasetId": "ds1"},
            [{"zestimate": 300_000, "price": 64706, "hdpUrl": "/homedetails/x/1_zpid/"}],
        )

    monkeypatch.setenv("APIFY_TOKEN", "dummy")
    monkeypatch.setenv("APIFY_ACTOR_ID", "ENK9p4RZHg0iVso52")
    monkeypatch.delenv("APIFY_INPUT_JSON", raising=False)
    monkeypatch.setattr("zestimate_agent.apify_backend._run_actor_and_collect", fake_run)

    result = fetch_zestimate_apify("32 Winspear Ave, Buffalo, NY 14214")
    assert result.zestimate == 300_000


def test_enk9_optional_dataset_id_and_start_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, Any]] = []

    def fake_run(
        _client: Any,
        _actor_id: str,
        run_input: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict]]:
        captured.append(run_input)
        return ({"id": "1", "defaultDatasetId": "ds1"}, [{"zestimate": 100, "hdpUrl": "/homedetails/x/1_zpid/"}])

    monkeypatch.setenv("APIFY_TOKEN", "dummy")
    monkeypatch.setenv("APIFY_ACTOR_ID", "ENK9p4RZHg0iVso52")
    monkeypatch.setenv("APIFY_SEARCH_RESULTS_DATASET_ID", "myDataset123")
    monkeypatch.setenv(
        "APIFY_START_URLS_JSON",
        '[{"url": "https://www.zillow.com/homedetails/foo/1_zpid/"}]',
    )
    monkeypatch.delenv("APIFY_INPUT_JSON", raising=False)
    monkeypatch.setattr("zestimate_agent.apify_backend._run_actor_and_collect", fake_run)

    fetch_zestimate_apify("18 Zelma Dr, Greenville, SC 29617")
    inp = captured[0]
    assert inp["searchResultsDatasetId"] == "myDataset123"
    assert len(inp["startUrls"]) == 1
