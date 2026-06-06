from __future__ import annotations

from typing import Any

import pytest

from cuenta.validator import ParsedInvoice, validate_all
from tests.support import loaded, make_raw


def test_valid_definition() -> None:
    valid, errors = validate_all([loaded("acme", make_raw())], active=["acme"])
    assert errors == []
    assert [v.key for v in valid] == ["acme"]


def test_missing_vendor_rejected() -> None:
    raw = make_raw()
    del raw["vendor"]
    _, errors = validate_all([loaded("acme", raw)], active=["acme"])
    assert any("vendor" in str(e) and "Field required" in str(e) for e in errors)


def test_bad_key_regex() -> None:
    _, errors = validate_all([loaded("bad", make_raw(key="Bad-Key"))], active=[])
    assert any("key" in str(e) and "should match pattern" in str(e) for e in errors)


def test_unknown_field_rejected() -> None:
    _, errors = validate_all([loaded("acme", make_raw(weird=True))], active=["acme"])
    assert any("weird" in str(e) and "Extra inputs are not permitted" in str(e) for e in errors)


def test_detect_list_of_strings_ok() -> None:
    _, errors = validate_all([loaded("acme", make_raw(detect=["A", "B"]))], active=["acme"])
    assert errors == []


def test_detect_empty_string_rejected() -> None:
    _, errors = validate_all([loaded("acme", make_raw(detect=""))], active=["acme"])
    assert any("detect" in str(e) for e in errors)


def test_parse_not_callable_rejected() -> None:
    _, errors = validate_all([loaded("acme", make_raw(parse="nope"))], active=["acme"])
    assert any("parse" in str(e) for e in errors)


def test_duplicate_keys_across_files() -> None:
    a = loaded("a", make_raw(key="dup"))
    b = loaded("b", make_raw(key="dup"))
    _, errors = validate_all([a, b], active=["dup"])
    assert any("duplicate key" in str(e) for e in errors)


def test_active_key_missing_reported() -> None:
    _, errors = validate_all([loaded("acme", make_raw())], active=["acme", "ghost"])
    assert any("ghost" in str(e) and "ACTIVE key" in str(e) for e in errors)


def test_parsed_invoice_requires_at_least_one_line(default_parse: dict[str, Any]) -> None:
    default_parse["lines"] = []
    with pytest.raises(ValueError):
        ParsedInvoice.model_validate(default_parse)


def test_parsed_invoice_rejects_bad_date(default_parse: dict[str, Any]) -> None:
    default_parse["date"] = "31/01/2026"
    with pytest.raises(ValueError):
        ParsedInvoice.model_validate(default_parse)


def test_parsed_line_rejects_extra_field(default_parse: dict[str, Any]) -> None:
    default_parse["lines"][0]["category"] = "compute"
    with pytest.raises(ValueError):
        ParsedInvoice.model_validate(default_parse)
