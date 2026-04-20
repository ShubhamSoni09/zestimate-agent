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
                    "PropertyAddress": {
                        "streetAddress": "7254 Wisteria Ln",
                        "city": "Lake Wales",
                        "state": "FL",
                        "zipcode": "33898",
                    },
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
        return (
            {"id": "1", "defaultDatasetId": "ds1"},
            [
                {
                    "zestimate": 1,
                    "PropertyAddress": {
                        "streetAddress": "7254 Wisteria Ln",
                        "city": "Lake Wales",
                        "state": "FL",
                        "zipcode": "33898",
                    },
                }
            ],
        )

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
                    "PropertyAddress": {
                        "streetAddress": "1 Bristol Ct #515",
                        "city": "San Francisco",
                        "state": "CA",
                        "zipcode": "94130",
                    },
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
                    "PropertyAddress": {
                        "streetAddress": "1483 Sutter St Unit 1507",
                        "city": "San Francisco",
                        "state": "CA",
                        "zipcode": "94109",
                    },
                },
                {
                    "message": "200: Success",
                    "zestimate": 1_227_800,
                    "PropertyZillowURL": "https://www.zillow.com/homedetails/15076475_zpid/",
                    "PropertyAddress": {
                        "streetAddress": "1483 Sutter St Unit 1507",
                        "city": "San Francisco",
                        "state": "CA",
                        "zipcode": "94109",
                    },
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
                        "PropertyAddress": {
                            "streetAddress": "unknown",
                            "city": "San Francisco",
                            "state": "CA",
                            "zipcode": "94109",
                        },
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
                    "PropertyAddress": {
                        "streetAddress": "1483 Sutter St #1507",
                        "city": "San Francisco",
                        "state": "CA",
                        "zipcode": "94109",
                    },
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


def test_hgph_actor_rejects_loose_nonmatching_listing(
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
                    "zestimate": 1_050_000,
                    "PropertyAddress": {
                        "streetAddress": "99 Example Ave",
                        "city": "New York",
                        "state": "NY",
                        "zipcode": "10001",
                    },
                    "PropertyZillowURL": "https://www.zillow.com/homedetails/not-the-one/123_zpid/",
                }
            ],
        )

    monkeypatch.setenv("APIFY_TOKEN", "dummy")
    monkeypatch.setenv("APIFY_ACTOR_ID", "HGPHGu8INtQpCeF3x")
    monkeypatch.setattr("zestimate_agent.apify_backend._run_actor_and_collect", fake_run)

    with pytest.raises(ValueError, match="Listing does not exist on Zillow"):
        fetch_zestimate_apify("32 George Ave, New York, NY 10001")


def test_hgph_actor_404_notfound_payload_returns_listing_missing_message(
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
                    "message": "404: NotFound",
                    "Source": "9vrc_2pxy_ncch",
                    "PropertyAddress": None,
                    "zestimate": None,
                    "Bedrooms": None,
                    "Bathrooms": None,
                    "Area(sqft)": None,
                    "PropertyZPID": None,
                    "Price": None,
                    "yearBuilt": None,
                    "daysOnZillow": None,
                    "PropertyZillowURL": None,
                }
            ],
        )

    monkeypatch.setenv("APIFY_TOKEN", "dummy")
    monkeypatch.setenv("APIFY_ACTOR_ID", "HGPHGu8INtQpCeF3x")
    monkeypatch.setattr("zestimate_agent.apify_backend._run_actor_and_collect", fake_run)

    with pytest.raises(ValueError, match="Listing does not exist on Zillow for address"):
        fetch_zestimate_apify("32 George Ave NYC NY 10001")
