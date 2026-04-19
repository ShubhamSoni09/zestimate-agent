from __future__ import annotations

import json
from pathlib import Path

import pytest

from zestimate_agent.eval_harness import (
    load_gold_cases,
    main,
    run_eval,
    zestimate_values_match,
)
from zestimate_agent.models import ZestimateResult


def test_zestimate_values_match_int() -> None:
    assert zestimate_values_match(123_000, 123_000) is True
    assert zestimate_values_match(123_000, 124_000) is False


def test_zestimate_values_match_not_available() -> None:
    assert zestimate_values_match("not_available", "not available") is True
    assert zestimate_values_match("not available", "not_available") is True
    assert zestimate_values_match("not_available", 500_000) is False


def test_load_gold_rejects_missing_expected_without_skip(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text(
        json.dumps({"version": 1, "cases": [{"id": "x", "address": "1 Main St, X, YY 00001"}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing expected"):
        load_gold_cases(p)


def test_run_eval_with_mock_agent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    gold = {
        "version": 1,
        "cases": [
            {
                "id": "a",
                "address": "1 Test St, Testville, TS 00001",
                "expected": 999,
                "verified_date": "2026-01-01",
            },
            {
                "id": "b",
                "address": "2 Test St, Testville, TS 00001",
                "expected": "not_available",
            },
        ],
    }
    gold_path = tmp_path / "gold.json"
    gold_path.write_text(json.dumps(gold), encoding="utf-8")

    class FakeAgent:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def get_zestimate(self, address: str) -> ZestimateResult:
            if "1 Test" in address:
                return ZestimateResult(
                    address=address,
                    zestimate=999,
                    property_url="https://www.zillow.com/homedetails/x/",
                )
            return ZestimateResult(
                address=address,
                zestimate="not available",
                property_url="https://www.zillow.com/homedetails/y/",
            )

    monkeypatch.setattr("zestimate_agent.client.ZillowEstimateAgent", FakeAgent)
    summary = run_eval(gold_path)
    assert summary["eligible"] == 2
    assert summary["passed"] == 2
    assert summary["failed"] == 0
    assert summary["pass_rate_percent"] == 100.0


def test_main_zero_exit_on_mock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gold = {
        "version": 1,
        "cases": [
            {
                "id": "only",
                "address": "9 Z St, Z, ZZ 99999",
                "expected": 1,
            },
        ],
    }
    p = tmp_path / "g.json"
    p.write_text(json.dumps(gold), encoding="utf-8")

    class MiniAgent:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def get_zestimate(self, addr: str) -> ZestimateResult:
            return ZestimateResult(address=addr, zestimate=1, property_url="u")

    monkeypatch.setattr("zestimate_agent.client.ZillowEstimateAgent", MiniAgent)
    assert main(["--gold", str(p)]) == 0
