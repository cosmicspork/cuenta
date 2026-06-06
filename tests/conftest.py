"""Fixtures. Reusable helper functions live in tests/support.py."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from tests.support import DEFAULT_PARSE


@pytest.fixture
def default_parse() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_PARSE)
