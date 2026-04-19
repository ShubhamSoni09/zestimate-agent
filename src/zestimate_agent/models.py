from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ZestimateValue = int | Literal["not available"]


@dataclass(frozen=True)
class ZestimateResult:
    address: str
    zestimate: ZestimateValue
    property_url: str
