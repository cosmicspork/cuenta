"""Validates definition contracts and the parse-output schema.

A definition describes one vendor's invoices. The per-definition contract is a
pydantic model (`InvoiceDefinition`); cross-definition checks (duplicate keys)
need the full set and live in `_cross_definition_checks`.

`parse` is a callable because PDF layouts vary too much for a declarative spec.
It receives the extracted text and returns a dict matching `ParsedInvoice`,
which the runner validates before emitting rows.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic import ValidationError as PydanticValidationError

from cuenta.loader import LoadedDefinition

NAME_PATTERN = r"^[a-z][a-z0-9_]*$"

SnakeCaseName = Annotated[str, Field(pattern=NAME_PATTERN)]
ISO_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


class ParsedLine(BaseModel):
    """One bucketed charge: an app (or "shared") and the amount attributed to it."""

    model_config = ConfigDict(extra="forbid")

    app: str = Field(min_length=1)
    amount: float
    note: str | None = None


class ParsedInvoice(BaseModel):
    """What a definition's `parse` callable must return."""

    model_config = ConfigDict(extra="forbid")

    invoice_no: str = Field(min_length=1)
    date: str = Field(pattern=ISO_DATE_PATTERN)
    total: float
    period: str | None = None
    lines: list[ParsedLine] = Field(min_length=1)


class InvoiceDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    key: SnakeCaseName
    vendor: str = Field(min_length=1)
    currency: str = "USD"
    # how to recognise this vendor's PDF text: substring, any-of substrings, or a predicate
    detect: str | list[str] | Callable[[str], bool]
    # text -> dict matching ParsedInvoice
    parse: Callable[[str], dict[str, Any]]

    @model_validator(mode="after")
    def _check_detect(self) -> InvoiceDefinition:
        # `parse` being callable is already enforced by its field type; only the
        # non-emptiness of `detect` needs a check pydantic can't express.
        if isinstance(self.detect, list) and not all(
            isinstance(s, str) and s for s in self.detect
        ):
            raise ValueError("`detect` list must contain only non-empty strings")
        if isinstance(self.detect, str) and not self.detect:
            raise ValueError("`detect` string must be non-empty")
        return self

    def matches(self, text: str) -> bool:
        d = self.detect
        if isinstance(d, str):
            return d in text
        if isinstance(d, list):
            return any(s in text for s in d)
        return bool(d(text))


@dataclass(frozen=True)
class ValidationError:
    source_path: Path | None
    key: str | None
    message: str

    def __str__(self) -> str:
        loc = self.source_path.name if self.source_path else "<config>"
        tag = f"{loc}:{self.key}" if self.key else loc
        return f"[{tag}] {self.message}"


@dataclass(frozen=True)
class ValidatedDefinition:
    source_path: Path
    definition: InvoiceDefinition

    @property
    def key(self) -> str:
        return self.definition.key


def validate_all(
    loaded: list[LoadedDefinition], active: list[str]
) -> tuple[list[ValidatedDefinition], list[ValidationError]]:
    valid: list[ValidatedDefinition] = []
    errors: list[ValidationError] = []

    for d in loaded:
        result = _parse_one(d.source_path, d.raw)
        if isinstance(result, list):
            errors.extend(result)
        else:
            valid.append(ValidatedDefinition(source_path=d.source_path, definition=result))

    errors.extend(_cross_definition_checks(valid, active))
    return valid, errors


def _parse_one(
    source_path: Path, raw: dict[str, Any]
) -> InvoiceDefinition | list[ValidationError]:
    raw_key = raw.get("key")
    key = raw_key if isinstance(raw_key, str) else None
    try:
        return InvoiceDefinition.model_validate(raw)
    except PydanticValidationError as exc:
        return _convert_pydantic_errors(exc, source_path, key)


def _convert_pydantic_errors(
    exc: PydanticValidationError, source_path: Path, key: str | None
) -> list[ValidationError]:
    out: list[ValidationError] = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"] if p != "function-after")
        msg = err["msg"].removeprefix("Value error, ")
        out.append(ValidationError(source_path, key, f"{loc}: {msg}" if loc else msg))
    return out


def _cross_definition_checks(
    valid: list[ValidatedDefinition], active: list[str]
) -> list[ValidationError]:
    errors: list[ValidationError] = []

    seen_keys: dict[str, Path] = {}
    for v in valid:
        if v.key in seen_keys:
            errors.append(
                ValidationError(
                    v.source_path,
                    v.key,
                    f"duplicate key {v.key!r}; first defined in {seen_keys[v.key].name}",
                )
            )
        else:
            seen_keys[v.key] = v.source_path

    valid_keys = {v.key for v in valid}
    for k in active:
        if k not in valid_keys:
            errors.append(
                ValidationError(None, k, f"ACTIVE key {k!r} is not defined or failed validation")
            )

    return errors
