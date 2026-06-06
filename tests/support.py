"""Shared test helpers: build definitions and a synthetic invoice without PDFs."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from cuenta.loader import LoadedDefinition
from cuenta.validator import InvoiceDefinition, ValidatedDefinition

DEFAULT_PARSE: dict[str, Any] = {
    "invoice_no": "ACME-1",
    "date": "2026-01-31",
    "total": 10.0,
    "period": "Jan 2026",
    "lines": [
        {"app": "alpha", "amount": 6.0, "note": "compute 6.00"},
        {"app": "shared", "amount": 4.0},
    ],
}


def make_raw(
    key: str = "acme",
    *,
    detect: Any = "ACME-INVOICE",
    parse: Callable[[str], dict[str, Any]] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "key": key,
        "vendor": "Acme",
        "detect": detect,
        "parse": parse if parse is not None else (lambda text: DEFAULT_PARSE),
    }
    base.update(overrides)
    return base


def loaded(name: str, raw: dict[str, Any]) -> LoadedDefinition:
    return LoadedDefinition(source_path=Path(f"definitions/{name}.py"), raw=raw)


def validated(raw: dict[str, Any], name: str = "acme") -> ValidatedDefinition:
    return ValidatedDefinition(
        source_path=Path(f"definitions/{name}.py"),
        definition=InvoiceDefinition.model_validate(raw),
    )
