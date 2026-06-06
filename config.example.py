"""Copy this to config.py and edit. config.py is gitignored (it names your
active vendors and points at your private invoice folder)."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

DEFINITIONS_DIR = REPO_ROOT / "definitions"  # one .py per vendor (gitignored)
INVOICES_DIR = REPO_ROOT / "invoices"  # drop PDFs here (gitignored)
OUTPUT_DIR = REPO_ROOT / "out"  # JSONL lands here (gitignored)

# Keys of the definitions to route invoices against.
ACTIVE: list[str] = [
    # "laravel_cloud",
]
