"""Routes each invoice PDF to the one active definition whose `detect` matches."""

from __future__ import annotations

from dataclasses import dataclass

from cuenta.validator import ValidatedDefinition


@dataclass(frozen=True)
class RouteResult:
    matched: ValidatedDefinition | None
    candidates: list[str]  # keys of every definition that matched (for ambiguity reports)


def route(text: str, active: list[ValidatedDefinition]) -> RouteResult:
    """Return the single definition matching this text, or report none / many."""
    hits = [d for d in active if d.definition.matches(text)]
    matched = hits[0] if len(hits) == 1 else None
    return RouteResult(matched=matched, candidates=[d.key for d in hits])
