import pytest

from zestimate_agent.apify_backend import fetch_zestimate_apify


def test_maxcopell_requires_searchquerystate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APIFY_TOKEN", "dummy")
    monkeypatch.setenv("APIFY_ACTOR_ID", "maxcopell/zillow-scraper")
    monkeypatch.setenv("APIFY_SYNTHETIC_SEARCH_URL", "0")
    monkeypatch.delenv("APIFY_INPUT_JSON", raising=False)
    monkeypatch.delenv("APIFY_ZILLOW_SEARCH_URL", raising=False)
    with pytest.raises(ValueError, match="searchQueryState"):
        fetch_zestimate_apify("32 Winspear Ave, Buffalo, NY 14214")


def test_maxcopell_requires_searchquerystate_in_env_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APIFY_TOKEN", "dummy")
    monkeypatch.setenv("APIFY_ACTOR_ID", "maxcopell/zillow-scraper")
    monkeypatch.setenv("APIFY_SYNTHETIC_SEARCH_URL", "0")
    monkeypatch.setenv(
        "APIFY_ZILLOW_SEARCH_URL",
        "https://www.zillow.com/homes/32-Winspear-Ave-Buffalo-NY_rb/",
    )
    monkeypatch.delenv("APIFY_INPUT_JSON", raising=False)
    with pytest.raises(ValueError, match="searchQueryState"):
        fetch_zestimate_apify("32 Winspear Ave")
