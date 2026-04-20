"""Unit tests for Apify backend URL building and JSON walking helpers."""

import pytest

from zestimate_agent import apify_backend
from zestimate_agent.apify_backend import (
    _walk_zestimate,
    _zillow_search_url,
)


def test_zillow_search_url_uses_percent_encoding_for_spaces() -> None:
    u = _zillow_search_url("32 Winspear Ave, Buffalo, NY 14214")
    assert " " not in u
    assert "+" not in u
    assert "%20" in u or "%2C" in u
    assert u.endswith("_rb/")


def test_walk_zestimate_nested() -> None:
    payload = {"listing": {"zestimate": 64706}}
    assert _walk_zestimate(payload) == 64706


def test_walk_zestimate_string_money() -> None:
    payload = {"priceEstimate": "$64,706"}
    assert _walk_zestimate(payload) == 64706


def test_dataset_item_limit_zero_means_unlimited(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APIFY_DATASET_ITEM_LIMIT", "0")
    assert apify_backend._dataset_item_limit() is None


def test_dataset_item_limit_numeric(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APIFY_DATASET_ITEM_LIMIT", "15")
    assert apify_backend._dataset_item_limit() == 15
