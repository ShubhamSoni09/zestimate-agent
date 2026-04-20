from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus, unquote, urlsplit, urlunsplit

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .address_validation import validate_us_property_address
from .extractor import extract_zestimate
from .models import ZestimateResult


class ZillowBlockedError(RuntimeError):
    """Raised when Zillow blocks the request with bot protection."""


def _normalize_browser_cookie(raw: dict) -> dict | None:
    """Convert Chrome/extension export to Playwright add_cookies shape."""
    name = raw.get("name")
    if not name:
        return None
    value = raw.get("value")
    if value is None:
        value = ""
    domain = raw.get("domain")
    path = raw.get("path") or "/"
    if not domain:
        return None
    out: dict = {
        "name": name,
        "value": value,
        "domain": domain,
        "path": path,
    }
    exp = raw.get("expirationDate")
    if isinstance(exp, (int, float)):
        out["expires"] = float(exp)
    http_only = raw.get("httpOnly")
    if isinstance(http_only, bool):
        out["httpOnly"] = http_only
    secure = raw.get("secure")
    if isinstance(secure, bool):
        out["secure"] = secure
    ss = raw.get("sameSite")
    if isinstance(ss, str):
        low = ss.lower()
        if low in ("lax", "strict"):
            out["sameSite"] = ss.capitalize()
        elif low in ("none", "no_restriction"):
            out["sameSite"] = "None"
            out["secure"] = True
    return out


def _cookies_from_parsed(parsed: object) -> list[dict]:
    if isinstance(parsed, dict) and "cookies" in parsed:
        items = parsed["cookies"]
    elif isinstance(parsed, list):
        items = parsed
    else:
        raise ValueError(
            "Cookies file must be a JSON array, or an object with a 'cookies' array "
            "(browser export format)."
        )
    if not isinstance(items, list):
        raise ValueError("Cookie list must be a JSON array.")
    normalized: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        n = _normalize_browser_cookie(item)
        if n:
            normalized.append(n)
    return normalized


def _project_root() -> Path:
    """Repo root in dev (src layout); in Docker use cwd (WORKDIR) or ZILLOW_DATA_DIR."""
    override = os.getenv("ZILLOW_DATA_DIR")
    if override:
        return Path(override)
    here = Path(__file__).resolve()
    dev_root = here.parents[2]
    if (dev_root / "pyproject.toml").is_file():
        return dev_root
    return Path.cwd()


def resolve_cookie_file_path(explicit: str | None = None) -> str | None:
    """Path to cookie JSON: explicit arg, then ZILLOW_COOKIES_FILE, then cookies/zillow.json."""
    if explicit:
        p = Path(explicit)
        return str(p) if p.is_file() else None
    env = os.getenv("ZILLOW_COOKIES_FILE")
    if env:
        p = Path(env)
        if p.is_file():
            return str(p)
    default = _project_root() / "cookies" / "zillow.json"
    if default.is_file():
        return str(default)
    return None


def _load_cookies(cookie_json: str | None, cookie_file: str | None) -> list[dict]:
    if cookie_json:
        parsed = json.loads(cookie_json)
        return _cookies_from_parsed(parsed)
    path = cookie_file or resolve_cookie_file_path()
    if path:
        with open(path, "r", encoding="utf-8") as handle:
            parsed = json.load(handle)
        return _cookies_from_parsed(parsed)
    return []


def _playwright_proxy_dict(
    raw: str | None,
    username: str | None,
    password: str | None,
) -> dict[str, str] | None:
    """Build Playwright proxy dict (Bright Data: http://host:port + username + password)."""
    if not raw:
        return None
    raw = raw.strip()
    if username is not None and password is not None:
        return {"server": raw, "username": username, "password": password}
    parsed = urlsplit(raw)
    if parsed.username or parsed.password:
        netloc = parsed.hostname or ""
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
        server = urlunsplit((parsed.scheme, netloc, parsed.path or "", "", ""))
        proxy: dict[str, str] = {"server": server}
        if parsed.username:
            proxy["username"] = unquote(parsed.username)
        if parsed.password:
            proxy["password"] = unquote(parsed.password)
        return proxy
    return {"server": raw}


def _playwright_proxy_from_env() -> dict[str, str] | None:
    return _playwright_proxy_dict(
        os.getenv("ZILLOW_PROXY_SERVER"),
        os.getenv("ZILLOW_PROXY_USERNAME"),
        os.getenv("ZILLOW_PROXY_PASSWORD"),
    )


def _retry_headed_when_blocked() -> bool:
    """If headless hits a bot wall, retry once with a visible browser (same cookies)."""
    raw = os.getenv("ZILLOW_RETRY_HEADED_ON_BLOCK", "1").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    if not raw:
        return True
    # Headed Chromium needs a display (Render/Fly/Docker typically have none → crash → 500).
    if sys.platform == "linux" and not os.getenv("DISPLAY", "").strip():
        if os.getenv("ZILLOW_ALLOW_HEADED_IN_CONTAINER", "").strip().lower() in (
            "1",
            "true",
            "yes",
        ):
            return True
        return False
    return True


def _delay_ms(env_name: str, default: int) -> int:
    """Fixed settle time after navigation (ms). Set to 0 to skip. Capped at 60s."""
    raw = os.getenv(env_name, "").strip()
    if raw.isdigit():
        return max(0, min(int(raw), 60_000))
    return default


def _skip_zillow_home_warmup() -> bool:
    """If true, go straight to the search URL (faster; may increase bot-wall rate for some sessions)."""
    raw = os.getenv("ZILLOW_SKIP_ZILLOW_HOME", "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _retry_backoff_sec() -> float:
    raw = os.getenv("ZILLOW_RETRY_BACKOFF_SEC", "").strip()
    if raw:
        try:
            v = float(raw)
            return max(0.0, min(v, 60.0))
        except ValueError:
            pass
    return 1.2


def _zillow_page_blocked(title: str, html: str) -> bool:
    """Detect Zillow bot-wall pages without matching normal listing HTML (e.g. 'captcha' in script URLs)."""
    t = (title or "").lower()
    if "access to this page has been denied" in t:
        return True
    h = html.lower()
    if "access to this page has been denied" in h:
        return True
    if "please verify you're a human" in h or "verify you're a human" in h:
        return True
    if "checking your browser before accessing" in h:
        return True
    return False


def _extract_property_link(page_url: str, html: str) -> str | None:
    if "/homedetails/" in page_url:
        return page_url
    links = re.findall(r'href="([^"]*?/homedetails/[^"]+)"', html, flags=re.IGNORECASE)
    if not links:
        return None
    first = links[0]
    if first.startswith("http"):
        return first
    return f"https://www.zillow.com{first}"


class ZillowEstimateAgent:
    def __init__(
        self,
        *,
        timeout_ms: int = 30000,
        max_retries: int = 3,
        proxy_server: str | None = None,
        cookies: list[dict] | None = None,
        headless: bool = True,
    ) -> None:
        if timeout_ms < 3000:
            raise ValueError("timeout_ms must be >= 3000")
        if max_retries < 1:
            raise ValueError("max_retries must be >= 1")
        self.timeout_ms = timeout_ms
        self.max_retries = max_retries
        env_to = os.getenv("ZILLOW_TIMEOUT_MS", "").strip()
        if env_to.isdigit():
            t = int(env_to)
            if t >= 3000:
                self.timeout_ms = min(t, 300_000)
        env_mr = os.getenv("ZILLOW_MAX_RETRIES", "").strip()
        if env_mr.isdigit():
            mr = int(env_mr)
            if mr >= 1:
                self.max_retries = min(mr, 10)
        self._proxy_override = proxy_server
        self.cookies = cookies if cookies is not None else _load_cookies(
            os.getenv("ZILLOW_COOKIES_JSON"),
            os.getenv("ZILLOW_COOKIES_FILE"),
        )
        self.headless = headless
        if os.getenv("ZILLOW_HEADLESS", "").strip().lower() in ("0", "false", "no"):
            self.headless = False

    def get_zestimate(self, address: str) -> ZestimateResult:
        clean_address = validate_us_property_address(address)

        backend = os.getenv("ZILLOW_BACKEND", "playwright").strip().lower()
        if backend == "apify":
            from .apify_backend import fetch_zestimate_apify

            return fetch_zestimate_apify(clean_address)

        search_url = f"https://www.zillow.com/homes/{quote_plus(clean_address)}_rb/"
        modes: list[bool] = [self.headless]
        if self.headless and _retry_headed_when_blocked():
            modes.append(False)

        zestimate: int | str | None = None
        property_url: str | None = None
        last_error: Exception | None = None
        completed = False

        for mi, headless_mode in enumerate(modes):
            for attempt in range(1, self.max_retries + 1):
                launch_kwargs: dict = {
                    "headless": headless_mode,
                    "args": ["--disable-blink-features=AutomationControlled"],
                }
                proxy_cfg = (
                    _playwright_proxy_dict(self._proxy_override, None, None)
                    if self._proxy_override
                    else _playwright_proxy_from_env()
                )
                if proxy_cfg:
                    launch_kwargs["proxy"] = proxy_cfg
                try:
                    with sync_playwright() as pw:
                        browser = pw.chromium.launch(**launch_kwargs)
                        ignore_https = bool(proxy_cfg)
                        context = browser.new_context(
                            viewport={"width": 1440, "height": 1200},
                            user_agent=(
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/131.0.0.0 Safari/537.36"
                            ),
                            locale="en-US",
                            timezone_id="America/New_York",
                            ignore_https_errors=ignore_https,
                            extra_http_headers={
                                "Accept-Language": "en-US,en;q=0.9",
                            },
                        )
                        if self.cookies:
                            try:
                                context.add_cookies(self.cookies)
                            except Exception as exc:
                                if os.getenv("ZILLOW_DEBUG"):
                                    raise ValueError(f"add_cookies failed: {exc}") from exc
                        page = context.new_page()
                        page.set_default_timeout(self.timeout_ms)
                        warmup_ms = _delay_ms("ZILLOW_WARMUP_MS", 800)
                        post_search_ms = _delay_ms("ZILLOW_POST_SEARCH_MS", 1500)
                        post_detail_ms = _delay_ms("ZILLOW_POST_DETAIL_MS", 1200)
                        if _skip_zillow_home_warmup():
                            page.goto(search_url, wait_until="domcontentloaded")
                        else:
                            page.goto("https://www.zillow.com/", wait_until="domcontentloaded")
                            if warmup_ms:
                                page.wait_for_timeout(warmup_ms)
                            page.goto(search_url, wait_until="domcontentloaded")

                        # Redirect often lands on a details page when address is unique.
                        if post_search_ms:
                            page.wait_for_timeout(post_search_ms)
                        pre_html = page.content()
                        pre_title = page.title()
                        if _zillow_page_blocked(pre_title, pre_html):
                            raise ZillowBlockedError(
                                "Zillow blocked this request (bot wall). "
                                "Cookies must usually match the IP Zillow sees: set ZILLOW_PROXY_* to a "
                                "US residential proxy, or run the API with ZILLOW_HEADLESS=0 on the same "
                                "machine where you exported cookies. If headless, a one-time headed retry "
                                "runs by default (disable with ZILLOW_RETRY_HEADED_ON_BLOCK=0)."
                            )
                        pu = page.url
                        resolved_link = _extract_property_link(pu, pre_html)
                        if resolved_link and resolved_link != pu:
                            page.goto(resolved_link, wait_until="domcontentloaded")
                            if post_detail_ms:
                                page.wait_for_timeout(post_detail_ms)
                            pu = page.url

                        html = page.content()
                        page_title = page.title()
                        if _zillow_page_blocked(page_title, html):
                            raise ZillowBlockedError(
                                "Zillow blocked this request on the property page (bot wall). "
                                "Use ZILLOW_PROXY_* (US residential) or ZILLOW_HEADLESS=0 on the cookie-export "
                                "machine; ZILLOW_RETRY_HEADED_ON_BLOCK=1 (default) retries once with a visible window."
                            )
                        z, _ex = extract_zestimate(html)

                        context.close()
                        browser.close()
                    zestimate = z
                    property_url = pu
                    completed = True
                    break
                except ZillowBlockedError:
                    if mi + 1 < len(modes):
                        break
                    raise
                except (PlaywrightTimeoutError, ValueError) as exc:
                    last_error = exc
                    if attempt == self.max_retries:
                        raise
                    time.sleep(_retry_backoff_sec())
            if completed:
                break

        if not completed:
            if last_error:
                raise last_error
            raise ValueError(
                "We could not get a Zestimate from Zillow after several tries. "
                "Check the address on Zillow, your network, and cookie or proxy settings if you use them, then try again."
            )

        return ZestimateResult(
            address=clean_address,
            zestimate=zestimate,
            property_url=property_url or search_url,
        )
