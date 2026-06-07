"""Per-PDF pipeline: extract -> route -> parse -> reconcile -> JSONL rows.

Failures are isolated per file so one unparseable invoice doesn't sink the batch.
A definition's `parse` output is validated against `ParsedInvoice`, and the
per-app lines must reconcile to the stated invoice total (within a cent) before
any rows are written for that file.
"""

from __future__ import annotations

import json
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TextIO

from pydantic import ValidationError as PydanticValidationError

from cuenta import extract, router
from cuenta.validator import InvoiceDefinition, ParsedInvoice, ValidatedDefinition

# Per-app line amounts must sum to the invoice total within this tolerance.
RECONCILE_TOLERANCE = 0.02


@dataclass
class RunResult:
    source: str
    status: Literal["ok", "error"]
    vendor: str | None = None
    invoice_no: str | None = None
    rows: int = 0
    total: float | None = None
    message: str | None = None
    traceback: str | None = None


def run_all(
    pdfs: list[Path],
    active: list[ValidatedDefinition],
    out_path: Path,
) -> list[RunResult]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    results: list[RunResult] = []
    with out_path.open("w", encoding="utf-8") as fh:
        for pdf in pdfs:
            results.append(_run_one(pdf, active, fh))
    return results


def _run_one(pdf: Path, active: list[ValidatedDefinition], fh: TextIO) -> RunResult:
    try:
        text = extract.pdf_to_text(pdf)

        rr = router.route(text, active)
        if rr.matched is None:
            if rr.candidates:
                return RunResult(
                    pdf.name, "error", message=f"matched multiple definitions: {rr.candidates}"
                )
            return RunResult(pdf.name, "error", message="no active definition matched this PDF")

        defn = rr.matched.definition
        raw = defn.parse(text)
        try:
            parsed = ParsedInvoice.model_validate(raw)
        except PydanticValidationError as e:
            return RunResult(
                pdf.name, "error", vendor=defn.vendor, message=f"parse output invalid: {e}"
            )

        line_sum = round(sum(line.amount for line in parsed.lines), 2)
        if abs(line_sum - parsed.total) > RECONCILE_TOLERANCE:
            return RunResult(
                pdf.name,
                "error",
                vendor=defn.vendor,
                invoice_no=parsed.invoice_no,
                total=parsed.total,
                message=f"reconciliation failed: lines sum {line_sum} != invoice total {parsed.total}",
            )

        rows = _emit_rows(defn, parsed, pdf.name)
        for row in rows:
            fh.write(json.dumps(row) + "\n")

        return RunResult(
            pdf.name,
            "ok",
            vendor=defn.vendor,
            invoice_no=parsed.invoice_no,
            rows=len(rows),
            total=parsed.total,
        )
    except Exception as e:
        return RunResult(
            pdf.name,
            "error",
            message=f"{type(e).__name__}: {e}",
            traceback=traceback.format_exc(),
        )


def _emit_rows(
    defn: InvoiceDefinition, parsed: ParsedInvoice, source: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in parsed.lines:
        row: dict[str, Any] = {
            "date": parsed.date,
            "vendor": defn.vendor,
            "app": line.app,
            "amount": round(line.amount, 2),
            "currency": defn.currency,
            "invoice_no": parsed.invoice_no,
            "period": parsed.period,
            "note": line.note,
            "source": source,
        }
        for name, fn in defn.computed.items():
            row[name] = fn(row)
        for key in defn.drop:
            row.pop(key, None)
        rows.append(row)
    return rows
