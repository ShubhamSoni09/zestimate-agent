from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ZestimateResult:
    address: str
    zestimate: int
    property_url: str
