# Zillow Estimate Agent

## Description

Takes a **US property address**, **Zillow property URL**, or **ZPID** and returns the **`zestimate`** value from Zillow (an **integer** when Zillow exposes one, or **`"not available"`** when it does not), plus the **property URL**.

Typical stack: **React + Vite** frontend (e.g. on Vercel) calling a **FastAPI** API (e.g. on Render) that uses **Apify** (`ZILLOW_BACKEND=apify`) to fetch listing data.

## Architecture

| Piece | Role |
|-------|------|
| **FastAPI** (`src/zestimate_agent/server.py`) | `POST /zestimate`, `GET /health`, CORS for the browser UI |
| **React + Vite** (`frontend/`) | Static UI; calls the API using `VITE_API_BASE_URL` in production |
| **Backend** | **Apify** actors via `ZILLOW_BACKEND=apify` (see `.env.example` for optional **Playwright** mode) |

Root **`vercel.json`**: install/build in `frontend/`, output `frontend/dist`. **`Dockerfile`**: runs the API with uvicorn.

## Setup

### 1. API (Python)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

Copy **`.env.example`** → **`.env`** in the project root. For Apify, set at least:

- `ZILLOW_BACKEND=apify`
- `APIFY_TOKEN=...`

Start the server:

```bash
python -m uvicorn zestimate_agent.server:app --host 127.0.0.1 --port 8000
```

If the UI is on another origin (e.g. Vercel), set **`CORS_ALLOW_VERCEL=1`** or **`CORS_ALLOW_ORIGINS`** on the API and restart.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

For production builds (Vercel), set **`VITE_API_BASE_URL`** to your API’s HTTPS origin (no trailing slash) and redeploy so the value is baked in at build time.

### 3. Optional — gold-label eval

```bash
pip install -e .
zestimate-eval
```

Uses **`eval/gold_labels.json`**. See that file and **`src/zestimate_agent/eval_harness.py`** for details.

## Notes

- **Secrets:** keep **`.env`** and **`cookies/`** (if used) out of git; they are gitignored for a reason.
- **Apify:** usage is billed on your plan; actor inputs and dataset shape can change — use **`APIFY_INPUT_JSON`** and Apify run logs when something breaks.
- **CORS:** after changing **`CORS_*`** on the API host, **restart** the process so browsers pick up the new rules.
- **Vercel:** **`VITE_*`** vars are read at **build** time — change them in the Vercel dashboard, then **redeploy** the frontend.
- **Caching:** successful **`/zestimate`** responses can be cached in memory (**`ZESTIMATE_CACHE_TTL_SECS`**, default 300s). Set **`0`** to disable if you need always-fresh values.
- **Zestimate field:** the API uses Zillow’s **`zestimate`** field only (no substitute from list price or tax value). If Zillow has no public Zestimate, the API returns **`"not available"`**.
- **Accuracy claims:** any pass rate comes from **`zestimate-eval`** over your gold file — expand **`eval/gold_labels.json`** with verified expectations before reporting a percentage.
