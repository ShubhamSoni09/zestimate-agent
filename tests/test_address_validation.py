import pytest

from zestimate_agent.address_validation import validate_us_property_address


def test_accepts_nyc_high_rise_style() -> None:
    a = validate_us_property_address("350 5th Ave, New York, NY 10118")
    assert a == "350 5th Ave, New York, NY 10118"


def test_accepts_buffalo_style() -> None:
    assert validate_us_property_address("32 Winspear Ave, Buffalo, NY 14214")


def test_accepts_zillow_url() -> None:
    u = "https://www.zillow.com/homedetails/foo/132916029_zpid/"
    assert validate_us_property_address(u) == u


def test_accepts_zpid() -> None:
    assert validate_us_property_address("132916029") == "132916029"


def test_accepts_zip_plus_four() -> None:
    assert validate_us_property_address("1 Main St, Austin, TX 78701-1234")


def test_accepts_comma_free_buffalo_style() -> None:
    assert (
        validate_us_property_address("32 Winspear Ave Buffalo ny 14214")
        == "32 Winspear Ave Buffalo ny 14214"
    )


def test_normalizes_internal_whitespace() -> None:
    assert validate_us_property_address("32  Winspear   Ave Buffalo NY 14214") == (
        "32 Winspear Ave Buffalo NY 14214"
    )


def test_rejects_bare_zip() -> None:
    with pytest.raises(ValueError, match="ZIP"):
        validate_us_property_address("14214")


def test_rejects_non_zillow_http_url() -> None:
    with pytest.raises(ValueError, match="Zillow"):
        validate_us_property_address("https://example.com/listing")


def test_rejects_too_short() -> None:
    with pytest.raises(ValueError, match="short"):
        validate_us_property_address("NY")


def test_rejects_gibberish() -> None:
    with pytest.raises(ValueError, match="US-style"):
        validate_us_property_address("hello world")
