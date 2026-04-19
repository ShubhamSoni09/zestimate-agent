# Zillow Estimate Agent

Takes a **US property address** and returns the **Zillow Zestimate** (integer) plus the **property URL**.

**Backends**

- **Playwright** (default): loads Zillow in Chromium, reads structured data (`JSON-LD`, `__NEXT_DATA__`), with label-based fallback.
- **Apify** (optional): set `ZILLOW_BACKEND=apify` so `/zestimate` uses your Apify actor instead of a local browser.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -e ".[dev]"
playwright install chromium
```

For Apify: `pip install -e ".[apify]"` and set `APIFY_TOKEN` (see below).

## CLI

```bash
zestimate-agent "1600 Amphitheatre Pkwy, Mountain View, CA 94043"
```

## HTTP API

```bash
python -m uvicorn zestimate_agent.server:app --host 127.0.0.1 --port 8000
```

```bash
curl -s http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/zestimate -H "Content-Type: application/json" -d "{\"address\":\"1600 Amphitheatre Pkwy, Mountain View, CA 94043\"}"
```

`POST /zestimate` returns JSON: `address`, `zestimate`, `property_url`. Invalid addresses return **400**; Zillow bot-wall responses return **403** when detected.

## Configuration

Copy `.env.example` to `.env` in the project root (loaded automatically).

| Variable | Purpose |
|----------|---------|
| `ZILLOW_BACKEND` | `playwright` (default) or `apify` |
| `ZILLOW_PROXY_SERVER`, `ZILLOW_PROXY_USERNAME`, `ZILLOW_PROXY_PASSWORD` | Optional proxy for Playwright |
| `ZILLOW_COOKIES_FILE` / `ZILLOW_COOKIES_JSON` | Optional cookies; default file `cookies/zillow.json` (gitignored) |
| `ZILLOW_HEADLESS`, `ZILLOW_RETRY_HEADED_ON_BLOCK` | Browser visibility and one-shot headed retry after a block |
| `CORS_ALLOW_ORIGINS` | Comma-separated origins for the React UI (default includes Vite dev URLs) |

**Speed (Playwright):** each request currently waits on fixed “settle” timers after navigation (defaults total a few seconds). Lower them or skip the first Zillow homepage hop:

| Variable | Default | Effect |
|----------|---------|--------|
| `ZILLOW_SKIP_ZILLOW_HOME` | off | Set `1` to open the search URL directly (saves one full page load; may hurt reliability without cookies/proxy). |
| `ZILLOW_WARMUP_MS` | `800` | Wait after `zillow.com` before search (ignored when skip-home is on). |
| `ZILLOW_POST_SEARCH_MS` | `1500` | Wait after the search URL loads before reading HTML. |
| `ZILLOW_POST_DETAIL_MS` | `1200` | Wait after navigating to a homedetails link. |
| `ZILLOW_TIMEOUT_MS` | `30000` | Playwright navigation timeout (min `3000`, cap `300000`). |
| `ZILLOW_MAX_RETRIES` | `3` | Fewer retries fail faster on bad addresses (cap `10`). |
| `ZILLOW_RETRY_BACKOFF_SEC` | `1.2` | Sleep between retry attempts. |

Example (aggressive; tune if extraction fails):

```text
ZILLOW_SKIP_ZILLOW_HOME=1
ZILLOW_POST_SEARCH_MS=400
ZILLOW_POST_DETAIL_MS=300
```

**Apify:** wall time is mostly the actor run. You cannot make Zillow faster locally; keep `APIFY_WAIT_SECS` only as high as needed. Prefer a small, focused actor and warm runs on Apify if your plan allows.

**Apify** (`ZILLOW_BACKEND=apify`): set `APIFY_TOKEN`. Default actor id is **`ENK9p4RZHg0iVso52`** (input: `startUrls`, `addresses`, `propertyStatus`, `extractBuildingUnits`). Override with `APIFY_ACTOR_ID`. Other actors (e.g. HGPH, maxcopell) are supported via the same env knobs documented in `.env.example`. If the dataset is empty, paste the actor’s exact input into `APIFY_INPUT_JSON`.

Optional tuning: `APIFY_WAIT_SECS`, `APIFY_ACTOR_TIMEOUT_SECS`, `APIFY_PROPERTY_STATUS`, `APIFY_EXTRACT_BUILDING_UNITS`, `APIFY_START_URLS_JSON`, `APIFY_SEARCH_RESULTS_DATASET_ID`.

## React UI

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. Set `VITE_API_BASE_URL` at build time if the API is not `http://127.0.0.1:8000`.

## Python API

```python
from zestimate_agent import ZillowEstimateAgent

agent = ZillowEstimateAgent(timeout_ms=30000)
result = agent.get_zestimate("1600 Amphitheatre Pkwy, Mountain View, CA 94043")
print(result.zestimate, result.property_url)
```

## Docker

From the project root (with `.env` and optional `cookies/` mount as in `docker-compose.yml`):

```bash
docker compose up --build
```

API on port **8000**. Use HTTPS and `CORS_ALLOW_ORIGINS` in production.

## Tests

```bash
pytest
```

## Publish to GitHub

1. Create a **new empty repository** on GitHub (no README/license if you already have them here).
2. From this project folder:

```bash
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git push -u origin main
```

`.env` and `cookies/*.json` stay local (see `.gitignore`). Pushes to `main` run **CI** (`.github/workflows/ci.yml`: install package + `pytest`).

## Notes

- Zillow may block scrapers; cookies aligned with **IP** (e.g. US residential proxy) improve Playwright reliability.
- Apify usage is billed on your plan; actor output shapes can change—use tests and `APIFY_INPUT_JSON` when debugging empty datasets.
