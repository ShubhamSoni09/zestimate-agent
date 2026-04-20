"""Normalize and validate US-style street addresses for property lookup."""

from __future__ import annotations

import re

# US state / territory abbreviations commonly used on Zillow mailing addresses
_US_STATE_ABBR = (
    "AK|AL|AR|AZ|CA|CO|CT|DC|DE|FL|GA|HI|IA|ID|IL|IN|KS|KY|LA|"
    "MA|MD|ME|MI|MN|MO|MS|MT|NC|ND|NE|NH|NJ|NM|NV|NY|OH|OK|OR|PA|"
    "PR|RI|SC|SD|TN|TX|UT|VA|VI|VT|WA|WI|WV|WY"
)

_RE_STATE = re.compile(rf"\b(?:{_US_STATE_ABBR})\b", re.IGNORECASE)
_RE_ZIP_END = re.compile(r"\b\d{5}(?:-\d{4})?\s*$")
def validate_us_property_address(raw: str) -> str:
    """
    Accept US-style street addresses: e.g. "350 5th Ave, New York, NY 10118"
      or comma-free "32 Winspear Ave Buffalo NY 14214" (internal spaces collapsed).
    """
    s = re.sub(r"\s+", " ", (raw or "").strip())
    if len(s) < 3:
        raise ValueError("Address is too short.")
    if len(s) > 500:
        raise ValueError("Address is too long (max 500 characters).")

    if _RE_STATE.search(s):
        return s

    if _RE_ZIP_END.search(s):
        # Reject a lone ZIP (still allow "32 ... Buffalo ny 14214").
        if re.fullmatch(r"\d{5}(?:-\d{4})?", s):
            raise ValueError(
                "Enter a full street address, not only a ZIP code."
            )
        return s

    if "," in s and re.search(r"\d", s) and len(s) >= 10:
        return s

    raise ValueError(
        "Enter a US-style property address (street, city, ST and ZIP)."
    )
