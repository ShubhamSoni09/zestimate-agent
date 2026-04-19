from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .env import load_project_dotenv

load_project_dotenv()

from .address_validation import validate_us_property_address
from .client import ZillowBlockedError, ZillowEstimateAgent, resolve_cookie_file_path


class ZestimateRequest(BaseModel):
    address: str = Field(..., min_length=1, description="US property address")


class ZestimateResponse(BaseModel):
    address: str
    zestimate: int
    property_url: str


def _cors_origins() -> list[str]:
    raw = os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    return [o.strip() for o in raw.split(",") if o.strip()]


app = FastAPI(title="Zillow Estimate Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "backend": os.getenv("ZILLOW_BACKEND", "playwright"),
        "apify_configured": str(bool(os.getenv("APIFY_TOKEN", "").strip())).lower(),
        "proxy_configured": str(bool(os.getenv("ZILLOW_PROXY_SERVER"))).lower(),
        "cookies_configured": str(
            bool(os.getenv("ZILLOW_COOKIES_JSON") or resolve_cookie_file_path())
        ).lower(),
    }


@app.post("/zestimate", response_model=ZestimateResponse)
def zestimate(req: ZestimateRequest) -> ZestimateResponse:
    try:
        address = validate_us_property_address(req.address)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    agent = ZillowEstimateAgent()
    try:
        result = agent.get_zestimate(address)
    except ZillowBlockedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal error") from exc
    return ZestimateResponse(**result.__dict__)

