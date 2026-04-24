from __future__ import annotations

import logging
import os
import sys
import threading

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Literal

from .env import load_project_dotenv

load_project_dotenv()

from .address_validation import validate_us_property_address
from .client import ZillowEstimateAgent
from .response_cache import get_cached, set_cached

logger = logging.getLogger(__name__)
_inflight_lock = threading.Lock()
_inflight_events: dict[str, threading.Event] = {}

try:
    from apify_client.errors import ApifyClientError as _ApifyClientError
except ImportError:
    _ApifyClientError = None


class ZestimateRequest(BaseModel):
    address: str = Field(..., min_length=1, description="US property address")


class ZestimateResponse(BaseModel):
    address: str
    zestimate: int | Literal["not available"]
    property_url: str


_DEFAULT_CORS = "http://localhost:5173,http://127.0.0.1:5173"


def _truthy_env(name: str) -> bool:
    raw = os.getenv(name, "")
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _zillow_debug_errors() -> bool:
    """When true, POST /zestimate may return exception text in JSON detail (avoid in public prod)."""
    return _truthy_env("ZILLOW_DEBUG")


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", _DEFAULT_CORS)
    out: list[str] = []
    for part in raw.replace(";", ",").split(","):
        o = part.strip().rstrip("/")
        if o:
            out.append(o)
    # Empty/mis-set env would deny every Origin and break preflight with 400 + CORS errors.
    if not out:
        return [o.strip().rstrip("/") for o in _DEFAULT_CORS.split(",") if o.strip()]
    return out


def _cors_origin_regex() -> str | None:
    custom = os.getenv("CORS_ALLOW_ORIGIN_REGEX", "").strip()
    if custom:
        return custom
    if _truthy_env("CORS_ALLOW_VERCEL"):
        # Production + preview: https://<name>.vercel.app and https://<name>-git-*.vercel.app
        return r"^https://[a-zA-Z0-9._-]+\.vercel\.app$"
    return None


app = FastAPI(title="Zillow Estimate Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_origin_regex=_cors_origin_regex(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, object]:
    """Avoid bare `{"detail":"Not Found"}` when someone opens the Render URL in a browser."""
    return {
        "service": app.title,
        "version": app.version,
        "docs": "/docs",
        "health": "/health",
        "zestimate": "POST /zestimate JSON body: {\"address\": \"...\"}",
    }


@app.get("/health")
def health() -> dict[str, str]:
    mode = ZillowEstimateAgent.backend_mode()
    backend_env = os.getenv("ZESTIMATE_BACKEND", "").strip().lower() or "auto"
    return {
        "status": "ok",
        "backend": mode,
        "apify_configured": str(bool(os.getenv("APIFY_TOKEN", "").strip())).lower(),
        "zestimate_backend_env": backend_env,
        "zillow_debug": str(_zillow_debug_errors()).lower(),
    }


@app.post("/zestimate", response_model=ZestimateResponse)
def zestimate(req: ZestimateRequest) -> ZestimateResponse:
    try:
        address = validate_us_property_address(req.address)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    cached = get_cached(address)
    if cached is not None:
        return ZestimateResponse(**cached.__dict__)
    should_fetch = False
    with _inflight_lock:
        event = _inflight_events.get(address)
        if event is None:
            event = threading.Event()
            _inflight_events[address] = event
            should_fetch = True
    if not should_fetch:
        event.wait()
        cached_after_wait = get_cached(address)
        if cached_after_wait is not None:
            return ZestimateResponse(**cached_after_wait.__dict__)
    if should_fetch:
        agent = ZillowEstimateAgent()
        try:
            result = agent.get_zestimate(address)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            if isinstance(exc, RuntimeError) and "apify-client" in str(exc).lower():
                # apify_backend wraps missing apify-client ImportError
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            if _ApifyClientError is not None and isinstance(exc, _ApifyClientError):
                logger.exception("POST /zestimate Apify client error")
                try:
                    sys.stderr.write(
                        f"POST /zestimate Apify error: {type(exc).__name__}: {exc}\n"
                    )
                    sys.stderr.flush()
                except OSError:
                    pass
                raise HTTPException(
                    status_code=502,
                    detail=str(exc)[:8000],
                ) from exc
            logger.exception("POST /zestimate failed")
            try:
                sys.stderr.write(
                    f"POST /zestimate failed: {type(exc).__name__}: {exc}\n"
                )
                sys.stderr.flush()
            except OSError:
                pass
            if _zillow_debug_errors():
                raise HTTPException(status_code=500, detail=str(exc)) from exc
            raise HTTPException(status_code=500, detail="Internal error") from exc
        finally:
            with _inflight_lock:
                inflight_event = _inflight_events.pop(address, None)
                if inflight_event is not None:
                    inflight_event.set()
        # Cache only successful numeric values; avoid pinning transient "not available" misses.
        if isinstance(result.zestimate, int):
            set_cached(address, result)
        return ZestimateResponse(**result.__dict__)
    # Another in-flight call finished but did not produce a cacheable result.
    agent = ZillowEstimateAgent()
    try:
        result = agent.get_zestimate(address)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        if isinstance(exc, RuntimeError) and "apify-client" in str(exc).lower():
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if _ApifyClientError is not None and isinstance(exc, _ApifyClientError):
            logger.exception("POST /zestimate Apify client error")
            raise HTTPException(status_code=502, detail=str(exc)[:8000]) from exc
        logger.exception("POST /zestimate failed")
        if _zillow_debug_errors():
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        raise HTTPException(status_code=500, detail="Internal error") from exc
    if isinstance(result.zestimate, int):
        set_cached(address, result)
    return ZestimateResponse(**result.__dict__)

