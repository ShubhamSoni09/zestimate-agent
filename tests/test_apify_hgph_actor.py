from __future__ import annotations

from typing import Any

import pytest

from zestimate_agent.apify_backend import fetch_zestimate_apify


def test_hgph_actor_sends_property_addresses_input_for_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    assert captured[0]["scrape_type"] == "property_addresses"
    assert captured[0]["multiple_input_box"] == "7254 Wisteria Ln, Lake Wales, FL 33898"


def test_hgph_actor_ignores_api_scrape_type_override(monkeypatch: pytest.MonkeyPatch) -> None:
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

    fetch_zestimate_apify("7254 Wisteria Ln, Lake Wales, FL 33898")
    assert captured[0]["scrape_type"] == "property_addresses"


def test_hgph_actor_sample_payload_maps_numeric_zestimate(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(
        _client: Any,
        _actor_id: str,
        _run_input: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict]]:
        return (
            {"id": "1", "defaultDatasetId": "ds1"},
            [
                {
                    "message": "200: Success",
                    "Source": "9vrc_gh1_2pxy_ncch",
                    "PropertyAddress": {
                        "streetAddress": "1 Bristol Ct #515",
                        "city": "San Francisco",
                        "state": "CA",
                        "zipcode": "94130",
                    },
                    "zestimate": 1_238_000,
                    "PropertyZillowURL": "https://www.zillow.com/homedetails/338980398_zpid/",
                }
            ],
        )

    monkeypatch.setenv("APIFY_TOKEN", "dummy")
    monkeypatch.setenv("APIFY_ACTOR_ID", "HGPHGu8INtQpCeF3x")
    monkeypatch.setattr("zestimate_agent.apify_backend._run_actor_and_collect", fake_run)

    result = fetch_zestimate_apify("1 Bristol Ct #515, San Francisco, CA 94130")
    assert result.zestimate == 1_238_000


def test_hgph_actor_nonnumeric_zestimate_returns_not_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(
        _client: Any,
        _actor_id: str,
        _run_input: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict]]:
        return (
            {"id": "1", "defaultDatasetId": "ds1"},
            [
                {
                    "message": "200: Success",
                    "zestimate": "N/A",
                    "PropertyZillowURL": "https://www.zillow.com/homedetails/338980398_zpid/",
                }
            ],
        )

    monkeypatch.setenv("APIFY_TOKEN", "dummy")
    monkeypatch.setenv("APIFY_ACTOR_ID", "HGPHGu8INtQpCeF3x")
    monkeypatch.setattr("zestimate_agent.apify_backend._run_actor_and_collect", fake_run)

    result = fetch_zestimate_apify("1 Bristol Ct #515, San Francisco, CA 94130")
    assert result.zestimate == "not available"


def test_hgph_actor_uses_later_row_numeric_zestimate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(
        _client: Any,
        _actor_id: str,
        _run_input: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict]]:
        return (
            {"id": "1", "defaultDatasetId": "ds1"},
            [
                {
                    "message": "200: Success",
                    "zestimate": None,
                    "PropertyZillowURL": "https://www.zillow.com/homedetails/15076475_zpid/",
                },
                {
                    "message": "200: Success",
                    "zestimate": 1_227_800,
                    "PropertyZillowURL": "https://www.zillow.com/homedetails/15076475_zpid/",
                },
            ],
        )

    monkeypatch.setenv("APIFY_TOKEN", "dummy")
    monkeypatch.setenv("APIFY_ACTOR_ID", "HGPHGu8INtQpCeF3x")
    monkeypatch.setattr("zestimate_agent.apify_backend._run_actor_and_collect", fake_run)

    result = fetch_zestimate_apify("1483 Sutter St Unit 1507, San Francisco, CA 94109")
    assert result.zestimate == 1_227_800


def test_hgph_actor_retries_with_unit_hash_variant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_run(
        _client: Any,
        _actor_id: str,
        run_input: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict]]:
        calls.append(run_input)
        if len(calls) == 1:
            return (
                {"id": "1", "defaultDatasetId": "ds1"},
                [
                    {
                        "message": "404: NotFound",
                        "zestimate": None,
                        "PropertyZillowURL": None,
                    }
                ],
            )
        return (
            {"id": "2", "defaultDatasetId": "ds2"},
            [
                {
                    "message": "200: Success",
                    "zestimate": 1_227_800,
                    "PropertyZillowURL": "https://www.zillow.com/homedetails/15076475_zpid/",
                }
            ],
        )

    monkeypatch.setenv("APIFY_TOKEN", "dummy")
    monkeypatch.setenv("APIFY_ACTOR_ID", "HGPHGu8INtQpCeF3x")
    monkeypatch.setattr("zestimate_agent.apify_backend._run_actor_and_collect", fake_run)

    result = fetch_zestimate_apify("1483 Sutter St Unit 1507, San Francisco, CA 94109")
    assert result.zestimate == 1_227_800
    assert len(calls) >= 2
    assert calls[0]["multiple_input_box"] == "1483 Sutter St Unit 1507, San Francisco, CA 94109"
    assert calls[1]["multiple_input_box"] == "1483 Sutter St #1507, San Francisco, CA 94109"
