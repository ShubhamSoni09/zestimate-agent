# Zillow Estimate Agent

Takes a **US property address**, **Zillow property URL**, or **ZPID** and returns the **Zillow Zestimate** (integer) plus the **property URL**.

## Architecture

| Piece | Role |
|-------|------|
| **FastAPI** (`src/zestimate_agent/server.py`) | `POST /zestimate`, `GET /health`, CORS for the UI |
| **React + Vite** (`frontend/`) | Static UI; talks to the API over HTTPS |
| **Backends** | **Playwright** (Chromium + HTML parsing) or **Apify** (`ZILLOW_BACKEND=apify`) |

Typical production layout:

- **Frontend:** [Vercel](https://vercel.com/) — build uses root `vercel.json` (install/build in `frontend/`, output `frontend/dist`).
- **API:** [Render](https://render.com/), Docker, or any host running `uvicorn` (see `Dockerfile`).

The browser calls your **API origin** directly, so you must configure **CORS** on the API and **`VITE_API_BASE_URL`** on Vercel at build time.

## Local development

### Python API

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
playwright install chromium
python -m uvicorn zestimate_agent.server:app --host 127.0.0.1 --port 8000
```

- **`apify-client`** is included in the default package dependencies so `ZILLOW_BACKEND=apify` works with a plain `pip install .` (e.g. on Render). Optional group `.[apify]` still exists for compatibility.

### React UI

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. In dev, the UI falls back to `http://127.0.0.1:8000` if `VITE_API_BASE_URL` is unset.

### CLI

```bash
zestimate-agent "1600 Amphitheatre Pkwy, Mountain View, CA 94043"
```

## HTTP API

```bash
curl -s http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/zestimate -H "Content-Type: application/json" -d "{\"address\":\"1600 Amphitheatre Pkwy, Mountain View, CA 94043\"}"
```

- **`POST /zestimate`** — body: `{"address":"..."}`. Response: `address`, `zestimate`, `property_url`.
- **`GET /health`** — `status`, `backend`, `apify_configured`, `proxy_configured`, `cookies_configured`, `zillow_debug` (whether `ZILLOW_DEBUG` is treated as on).
- Invalid input → **400**; detected Zillow block (Playwright) → **403**; Apify client errors → **502**; other server bugs → **500** (generic `"Internal error"` unless debug is on).

## Configuration

Copy `.env.example` to `.env` in the project root (loaded automatically by the API).

### Core

| Variable | Purpose |
|----------|---------|
| `ZILLOW_BACKEND` | `playwright` (default) or `apify` |
| `APIFY_TOKEN` | Required when `ZILLOW_BACKEND=apify` |
| `APIFY_ACTOR_ID` | Override default actor (`ENK9p4RZHg0iVso52`) |
| `ZILLOW_PROXY_SERVER`, `ZILLOW_PROXY_USERNAME`, `ZILLOW_PROXY_PASSWORD` | Optional proxy for Playwright |
| `ZILLOW_COOKIES_FILE` / `ZILLOW_COOKIES_JSON` | Optional cookies; default file `cookies/zillow.json` (gitignored) |
| `ZILLOW_HEADLESS`, `ZILLOW_RETRY_HEADED_ON_BLOCK` | Browser visibility and headed retry after a block |

### CORS (required when UI and API are on different origins)

| Variable | Purpose |
|----------|---------|
| `CORS_ALLOW_ORIGINS` | Comma-separated list, e.g. `https://your-app.vercel.app,http://localhost:5173` (no trailing slashes) |
| `CORS_ALLOW_VERCEL` | Set to `1` / `true` / `on` to allow preview and production `*.vercel.app` origins via regex |
| `CORS_ALLOW_ORIGIN_REGEX` | Advanced: custom origin regex |

If the browser shows a **CORS** error on preflight, the API rejected the `Origin` header — fix the variables above and **restart** the API process.

### Frontend (Vercel / any static host)

| Variable | When |
|----------|------|
| `VITE_API_BASE_URL` | **Required in production builds** — full HTTPS origin of the API, e.g. `https://your-api.onrender.com` (no trailing slash). Set in Vercel → Environment Variables and **redeploy** so Vite bakes it in. |
| `VITE_SITE_URL` | Optional — your **frontend** production origin (no trailing slash), e.g. `https://your-app.vercel.app`. Sets **canonical** and **`og:url`** after deploy. |
| `VITE_APP_TITLE` | Optional — browser tab title (default: “Zillow Zestimate Agent”). |

### API performance & debugging

| Variable | Purpose |
|----------|---------|
| `ZESTIMATE_CACHE_TTL_SECS` | Default `300`. Successful `/zestimate` responses are cached in memory for this many seconds so repeat lookups skip Apify/Playwright. Set `0` to disable. |
| `ZILLOW_DEBUG` | `1` / `true` / `yes` / `on` — include exception text in **500** `detail` (do **not** leave on in public production). |

**Playwright timing** (optional): `ZILLOW_SKIP_ZILLOW_HOME`, `ZILLOW_WARMUP_MS`, `ZILLOW_POST_SEARCH_MS`, `ZILLOW_POST_DETAIL_MS`, `ZILLOW_TIMEOUT_MS`, `ZILLOW_MAX_RETRIES`, `ZILLOW_RETRY_BACKOFF_SEC` — see `.env.example`.

**Apify tuning:** `APIFY_WAIT_SECS`, `APIFY_ACTOR_TIMEOUT_SECS`, `APIFY_PROPERTY_STATUS`, `APIFY_EXTRACT_BUILDING_UNITS`, `APIFY_START_URLS_JSON`, `APIFY_SEARCH_RESULTS_DATASET_ID`, `APIFY_INPUT_JSON`, etc. — see `.env.example`. Wall time is dominated by the actor run; the API also **reuses one `ApifyClient` per token** and can **serve cached** results when `ZESTIMATE_CACHE_TTL_SECS` is not `0`.

## Deployment

### Vercel (frontend)

1. Connect the repo; Vercel uses root **`vercel.json`**: `npm ci` / `npm run build` inside `frontend/`, publish `frontend/dist`.
2. Set **`VITE_API_BASE_URL`** to your public API URL (Production and Preview as needed).
3. Redeploy after changing env vars (Vite reads them at **build** time).

**Changing the site URL users see**

- The **address bar hostname** is controlled in **Vercel**, not in Git: **Project → Settings → Domains** (add a custom domain) or change the **project name** (updates the default `https://<name>.vercel.app` URL).
- After you know the **production** URL, set **`VITE_SITE_URL`** in Vercel to that exact origin (no trailing slash), e.g. `https://your-app.vercel.app`. Rebuild. The app will inject **`<link rel="canonical">`** and **`og:url`** so search and shares use the right URL.
- Optional: **`VITE_APP_TITLE`** overrides the browser tab title (default: “Zillow Zestimate Agent”).

### Render / Docker / generic (API)

**Docker** (from repo root; matches `Dockerfile`):

```bash
docker compose up --build
```

API listens on **8000**. Set production env vars (`CORS_*`, `ZILLOW_BACKEND`, `APIFY_TOKEN`, etc.) on the host.

**Render (example):**

- Build/install: e.g. `pip install .` from repo root (installs `apify-client` with the package).
- Start: `python -m uvicorn zestimate_agent.server:app --host 0.0.0.0 --port $PORT` (use Render’s **`$PORT`** if required by your service type).
- After changing env vars, **restart** or redeploy so CORS and debug flags apply.

## Python API (library)

```python
from zestimate_agent import ZillowEstimateAgent

agent = ZillowEstimateAgent(timeout_ms=30000)
result = agent.get_zestimate("1600 Amphitheatre Pkwy, Mountain View, CA 94043")
print(result.zestimate, result.property_url)
```

## Accuracy evaluation (gold labels)

The assignment asks for measurable accuracy against Zillow. This repo includes a **small harness** that compares the agent output to **frozen expected values** in `eval/gold_labels.json` (not live Zillow scraping during `pytest`).

1. Edit **`eval/gold_labels.json`**: for each case, set **`expected`** to the integer Zestimate (or `"not_available"` when Zillow’s `zestimate` field is null), set **`verified_date`**, and set **`skip`: false** when the row is ready to count.
2. Run from the **repository root** (with `.env` / proxy / Apify as needed for your backend):

```bash
zestimate-eval
# or
python -m zestimate_agent.eval_harness --gold eval/gold_labels.json --json-out eval/report.json
```

Exit codes: **0** = all eligible cases passed; **1** = at least one mismatch; **2** = file/config/runtime error; **3** = zero eligible cases (everything still skipped). The printed **`pass_rate_percent`** applies only to **non-skipped** cases.

Offline tests in `tests/test_eval_harness.py` validate parsing and matching logic with a **mock** agent (no network).

## Tests

```bash
pytest
```

CI (`.github/workflows/ci.yml`) installs the package and runs `pytest` on pushes to `main`.

## Notes

- Zillow may block scrapers; cookies aligned with **IP** (e.g. US residential proxy) improve Playwright reliability.
- Apify usage is billed on your plan; actor output shapes can change — use `APIFY_INPUT_JSON` and Apify run logs when debugging empty datasets.
- `.env` and `cookies/*.json` are gitignored; do not commit secrets.
