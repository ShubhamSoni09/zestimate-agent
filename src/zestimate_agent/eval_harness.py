"""
Offline / live evaluation against gold JSON labels.

Run from repo root (after pip install -e ".[dev]" and optional Playwright/Apify env):

  zestimate-eval --gold path/to/gold_labels.json
  zestimate-eval --gold path/to/gold_labels.json --json-out path/to/report.json

Exit 0 only when every non-skipped case matches. Skipped cases (skip: true or
expected: null) are reported but do not affect pass rate.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .env import load_project_dotenv


NA_DISPLAY = "not available"
_MISSING = object()


def _normalize_expected(raw: Any) -> int | str | None:
    """None means case not ready (must be skipped)."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    if isinstance(raw, str):
        t = raw.strip().lower().replace("-", "_")
        if t in ("not_available", "notavailable", NA_DISPLAY.replace(" ", "_")):
            return NA_DISPLAY
        digits = "".join(c for c in raw if c.isdigit())
        if digits:
            return int(digits)
    raise ValueError(f"Invalid expected value: {raw!r}")


def _normalize_actual(raw: Any) -> int | str:
    if raw is None:
        return NA_DISPLAY
    if isinstance(raw, str) and raw.strip().lower() in (
        "not_available",
        NA_DISPLAY.lower(),
        "notavailable",
    ):
        return NA_DISPLAY
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    if isinstance(raw, str):
        digits = "".join(c for c in raw if c.isdigit())
        if digits:
            return int(digits)
    return NA_DISPLAY


def zestimate_values_match(expected: int | str, actual: int | str) -> bool:
    e = _normalize_actual(expected)
    a = _normalize_actual(actual)
    if e == NA_DISPLAY and a == NA_DISPLAY:
        return True
    if isinstance(e, int) and isinstance(a, int):
        return e == a
    return False


@dataclass(frozen=True)
class GoldCaseRow:
    id: str
    address: str
    expected: int | str | None
    skip: bool
    verified_date: str | None
    notes: str | None


def load_gold_cases(path: Path) -> tuple[list[GoldCaseRow], dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "cases" not in data:
        raise ValueError("Gold file must be a JSON object with a 'cases' array.")
    raw_cases = data["cases"]
    if not isinstance(raw_cases, list):
        raise ValueError("'cases' must be an array.")
    out: list[GoldCaseRow] = []
    for i, row in enumerate(raw_cases):
        if not isinstance(row, dict):
            raise ValueError(f"cases[{i}] must be an object.")
        cid = str(row.get("id", f"case-{i}"))
        addr = row.get("address")
        if not isinstance(addr, str) or not addr.strip():
            raise ValueError(f"cases[{i}].id={cid!r} needs a non-empty string address.")
        skip_flag = bool(row.get("skip", False))
        exp_raw = row.get("expected", _MISSING)
        if exp_raw is _MISSING or exp_raw is None:
            exp_norm = None
            if not skip_flag:
                raise ValueError(
                    f"cases[{i}] id={cid!r}: missing expected — set skip:true or provide expected."
                )
        else:
            exp_norm = _normalize_expected(exp_raw)
        notes = row.get("notes")
        notes = str(notes) if notes is not None else None
        vd = row.get("verified_date")
        vd = str(vd) if vd is not None else None
        out.append(
            GoldCaseRow(
                id=cid,
                address=addr.strip(),
                expected=exp_norm,
                skip=skip_flag or exp_norm is None,
                verified_date=vd,
                notes=notes,
            )
        )
    return out, data


def run_eval(
    gold_path: Path,
    *,
    json_out: Path | None = None,
) -> dict[str, Any]:
    load_project_dotenv()
    from .client import ZillowEstimateAgent

    cases, raw_doc = load_gold_cases(gold_path)
    agent = ZillowEstimateAgent()
    results: list[dict[str, Any]] = []
    eligible = 0
    passed = 0
    skipped = 0

    for c in cases:
        if c.skip:
            skipped += 1
            results.append(
                {
                    "id": c.id,
                    "address": c.address,
                    "skipped": True,
                    "reason": c.notes or "skip flag or expected not set",
                }
            )
            continue
        assert c.expected is not None
        eligible += 1
        err: str | None = None
        actual_norm: int | str | None = None
        prop_url: str | None = None
        try:
            got = agent.get_zestimate(c.address)
            prop_url = got.property_url
            actual_norm = _normalize_actual(got.zestimate)
            ok = zestimate_values_match(c.expected, got.zestimate)
        except Exception as exc:
            ok = False
            err = f"{type(exc).__name__}: {exc}"
        if ok:
            passed += 1
        results.append(
            {
                "id": c.id,
                "address": c.address,
                "expected": c.expected,
                "actual": actual_norm,
                "match": ok,
                "property_url": prop_url,
                "error": err,
                "verified_date": c.verified_date,
            }
        )

    rate = (passed / eligible * 100.0) if eligible else 0.0
    summary = {
        "gold_file": str(gold_path.resolve()),
        "version": raw_doc.get("version"),
        "eligible": eligible,
        "passed": passed,
        "failed": eligible - passed,
        "skipped": skipped,
        "pass_rate_percent": round(rate, 2),
        "cases": results,
    }
    if json_out:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _print_summary(summary: dict[str, Any]) -> None:
    print(f"Gold file: {summary['gold_file']}")
    print(f"Eligible cases: {summary['eligible']}  Skipped: {summary['skipped']}")
    print(f"Passed: {summary['passed']}  Failed: {summary['failed']}")
    print(f"Pass rate (eligible only): {summary['pass_rate_percent']}%")
    for row in summary["cases"]:
        if row.get("skipped"):
            print(f"  [SKIP] {row['id']}: {row['address']}")
            continue
        mark = "OK" if row.get("match") else "FAIL"
        print(
            f"  [{mark}] {row['id']}: expected={row['expected']!r} actual={row.get('actual')!r}"
        )
        if row.get("error"):
            print(f"        error: {row['error']}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Evaluate agent vs a gold-labels JSON file.")
    p.add_argument(
        "--gold",
        type=Path,
        required=True,
        help="Path to gold labels JSON (schema: see eval_harness.load_gold_cases).",
    )
    p.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Write machine-readable report to this path.",
    )
    ns = p.parse_args(argv)
    path: Path = ns.gold
    if not path.is_file():
        print(f"Gold file not found: {path}", file=sys.stderr)
        return 2
    try:
        summary = run_eval(path, json_out=ns.json_out)
    except Exception as exc:
        print(f"Eval failed: {exc}", file=sys.stderr)
        return 2
    _print_summary(summary)
    if summary["eligible"] == 0:
        print(
            "\nNo eligible cases (all skipped). Add expected integers and skip:false to measure pass rate.",
            file=sys.stderr,
        )
        return 3
    if summary["failed"]:
        return 1
    return 0


def cli_entry() -> None:
    """Console script entry (propagates exit code)."""
    raise SystemExit(main())


if __name__ == "__main__":
    cli_entry()
