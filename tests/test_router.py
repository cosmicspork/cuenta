from __future__ import annotations

from cuenta.router import route
from tests.support import make_raw, validated


def test_single_match() -> None:
    acme = validated(make_raw(key="acme", detect="ACME"))
    other = validated(make_raw(key="other", detect="OTHER"), name="other")
    rr = route("this is an ACME bill", [acme, other])
    assert rr.matched is not None
    assert rr.matched.key == "acme"


def test_no_match() -> None:
    acme = validated(make_raw(key="acme", detect="ACME"))
    rr = route("nothing relevant here", [acme])
    assert rr.matched is None
    assert rr.candidates == []


def test_multiple_matches_is_ambiguous() -> None:
    a = validated(make_raw(key="a", detect="BILL"))
    b = validated(make_raw(key="b", detect="BILL"), name="b")
    rr = route("a BILL", [a, b])
    assert rr.matched is None
    assert sorted(rr.candidates) == ["a", "b"]


def test_detect_callable() -> None:
    acme = validated(make_raw(key="acme", detect=lambda t: t.count("x") >= 3))
    assert route("xxx", [acme]).matched is not None
    assert route("xx", [acme]).matched is None
