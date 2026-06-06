"""Turns an invoice PDF into text via `pdftotext -layout`."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class ExtractError(Exception):
    pass


def pdf_to_text(pdf_path: Path) -> str:
    """Extract layout-preserving text from a PDF.

    Layout mode keeps columns roughly aligned, which the line-item parsers rely
    on to find the trailing amount on each charge row.
    """
    exe = shutil.which("pdftotext")
    if exe is None:
        raise ExtractError(
            "pdftotext not found on PATH; install poppler "
            "(e.g. `brew install poppler` or `apt install poppler-utils`)"
        )
    try:
        result = subprocess.run(
            [exe, "-layout", "-enc", "UTF-8", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise ExtractError(f"pdftotext failed on {pdf_path.name}: {e.stderr.strip()}") from e
    return result.stdout
