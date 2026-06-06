from __future__ import annotations

from pathlib import Path

import pytest

from cuenta import extract


def test_missing_binary_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(extract.shutil, "which", lambda _name: None)
    with pytest.raises(extract.ExtractError, match="pdftotext not found"):
        extract.pdf_to_text(Path("whatever.pdf"))
