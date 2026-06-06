from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from cuenta import runner
from tests.support import make_raw, validated

CANNED_TEXT = "ACME-INVOICE body text"


@pytest.fixture(autouse=True)
def _patch_extract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner.extract, "pdf_to_text", lambda _p: CANNED_TEXT)


def _run(raw: dict[str, Any], tmp_path: Path) -> tuple[list[runner.RunResult], list[dict[str, Any]]]:
    out = tmp_path / "out.jsonl"
    results = runner.run_all([Path("invoices/x.pdf")], [validated(raw)], out)
    rows = [json.loads(line) for line in out.read_text().splitlines()] if out.exists() else []
    return results, rows


def test_ok_emits_rows_and_stamps_fields(tmp_path: Path) -> None:
    results, rows = _run(make_raw(), tmp_path)
    assert results[0].status == "ok"
    assert results[0].rows == 2
    assert {r["app"] for r in rows} == {"alpha", "shared"}
    row = next(r for r in rows if r["app"] == "alpha")
    assert row["vendor"] == "Acme"
    assert row["type"] == "expense"
    assert row["currency"] == "USD"
    assert row["invoice_no"] == "ACME-1"
    assert row["source"] == "x.pdf"


def test_reconciliation_failure_writes_no_rows(tmp_path: Path) -> None:
    bad = make_raw(
        parse=lambda _t: {
            "invoice_no": "ACME-2",
            "date": "2026-01-31",
            "total": 10.0,
            "lines": [{"app": "alpha", "amount": 6.0}],  # sums to 6, not 10
        }
    )
    results, rows = _run(bad, tmp_path)
    assert results[0].status == "error"
    assert "reconciliation failed" in (results[0].message or "")
    assert rows == []


def test_parser_exception_is_isolated(tmp_path: Path) -> None:
    def boom(_t: str) -> dict[str, Any]:
        raise ValueError("unmapped resource xyz")

    results, _ = _run(make_raw(parse=boom), tmp_path)
    assert results[0].status == "error"
    assert "unmapped resource xyz" in (results[0].message or "")


def test_invalid_parse_output_is_error(tmp_path: Path) -> None:
    bad = make_raw(parse=lambda _t: {"invoice_no": "X"})  # missing required fields
    results, rows = _run(bad, tmp_path)
    assert results[0].status == "error"
    assert "parse output invalid" in (results[0].message or "")
    assert rows == []


def test_no_definition_matches(tmp_path: Path) -> None:
    out = tmp_path / "out.jsonl"
    nomatch = validated(make_raw(detect="SOMETHING-ELSE"))
    results = runner.run_all([Path("invoices/x.pdf")], [nomatch], out)
    assert results[0].status == "error"
    assert "no active definition matched" in (results[0].message or "")
