import json

from zestimate_agent.client import _cookies_from_parsed


def test_browser_export_wrapper_format() -> None:
    raw = {
        "url": "https://www.zillow.com",
        "cookies": [
            {
                "domain": ".zillow.com",
                "expirationDate": 1811113493.235539,
                "hostOnly": False,
                "httpOnly": False,
                "name": "zguid",
                "path": "/",
                "sameSite": "unspecified",
                "secure": False,
                "session": False,
                "storeId": "0",
                "value": "test-value",
            }
        ],
    }
    out = _cookies_from_parsed(raw)
    assert len(out) == 1
    assert out[0]["name"] == "zguid"
    assert out[0]["value"] == "test-value"
    assert out[0]["domain"] == ".zillow.com"
    assert out[0]["expires"] == 1811113493.235539


def test_plain_array_still_works() -> None:
    raw = json.loads(
        '[{"name":"a","value":"b","domain":".zillow.com","path":"/","secure":true}]'
    )
    out = _cookies_from_parsed(raw)
    assert len(out) == 1
    assert out[0]["name"] == "a"
