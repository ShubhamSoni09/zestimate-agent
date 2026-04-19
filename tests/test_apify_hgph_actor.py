from __future__ import annotations

from typing import Any

import pytest

from zestimate_agent.apify_backend import fetch_zestimate_apify


def test_hgph_actor_sends_zpids_input(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, Any]] = []

    def fake_run(
        _client: Any,
        _actor_id: str,
        run_input: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict]]:
        captured.append(run_input)
        return (
            {"id": "1", "defaultDatasetId": "ds1"},
            [
                {
                    "zestimate": 350_000,
                    "url": "https://www.zillow.com/homedetails/foo/123_zpid/",
                }
            ],
        )

    monkeypatch.setenv("APIFY_TOKEN", "dummy")
    monkeypatch.setenv("APIFY_ACTOR_ID", "HGPHGu8INtQpCeF3x")
    monkeypatch.delenv("APIFY_INPUT_JSON", raising=False)
    monkeypatch.delenv("APIFY_SCRAPE_TYPE", raising=False)
    monkeypatch.setattr("zestimate_agent.apify_backend._run_actor_and_collect", fake_run)

    result = fetch_zestimate_apify("7254 Wisteria Ln, Lake Wales, FL 33898")
    assert result.zestimate == 350_000
    assert captured[0]["scrape_type"] == "zpids"
    assert captured[0]["multiple_input_box"] == "7254 Wisteria Ln, Lake Wales, FL 33898"


def test_hgph_actor_respects_api_scrape_type(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, Any]] = []

    def fake_run(
        _client: Any,
        _actor_id: str,
        run_input: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict]]:
        captured.append(run_input)
        return ({"id": "1", "defaultDatasetId": "ds1"}, [{"zestimate": 1}])

    monkeypatch.setenv("APIFY_TOKEN", "dummy")
    monkeypatch.setenv("APIFY_ACTOR_ID", "HGPHGu8INtQpCeF3x")
    monkeypatch.setenv("APIFY_SCRAPE_TYPE", "custom_mode")
    monkeypatch.delenv("APIFY_INPUT_JSON", raising=False)
    monkeypatch.setattr("zestimate_agent.apify_backend._run_actor_and_collect", fake_run)

    fetch_zestimate_apify("110083637")
    assert captured[0]["scrape_type"] == "custom_mode"
