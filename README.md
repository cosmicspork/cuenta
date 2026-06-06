# Cuenta

A small local tool that turns invoice PDFs into normalized line-item JSONL. Drop
a Python file per vendor into `definitions/`, drop PDFs into `invoices/`, run
`./run.sh`, and Cuenta routes each PDF to its vendor parser and writes one JSONL
file of rows ready to import into accounting. Built on the same patterns as
[mesa](https://github.com/cosmicspork/mesa) and
[carta](https://github.com/cosmicspork/carta).

## Why this exists

Cloud invoices are PDFs, and the number you actually want, what each project or
app cost, often isn't on the summary page. It's buried in per-resource line items
tagged with opaque ids. Reconstructing a clean expense ledger by hand, every
month, across several vendors, is the kind of small recurring chore that quietly
eats time.

Cuenta automates the middle. Each vendor becomes a Python file in `definitions/`
that knows how to read that vendor's invoice text and bucket the charges (for
example, splitting a shared cloud bill across the apps that ran on it). The
framework handles the boring glue: extracting text, routing each PDF to the
right parser, validating the result, and writing JSONL.

It deliberately stops at JSONL. Importing into your accounting system is a
separate step you control.

## Install

Requires [uv](https://github.com/astral-sh/uv), Python 3.13, and `pdftotext`
(from poppler: `brew install poppler` or `apt install poppler-utils`).

```bash
uv sync --extra dev
cp config.example.py config.py     # then edit ACTIVE
```

## Run

```bash
uv run cuenta                       # parse every PDF in INVOICES_DIR
uv run cuenta path/to/one.pdf       # parse specific file(s)
uv run cuenta --only acme_cloud     # route against a subset of ACTIVE
uv run pytest                       # tests
uv run ruff check .                 # lint
uv run mypy cuenta                  # type check
```

The `run.bat` (Windows) and `run.sh` (Unix) wrappers exist for double-click runs
without opening a terminal. Each run writes a timestamped `out/<date_time>.jsonl`.

## What you'll edit

| File / folder | Purpose |
|---|---|
| `config.py` | The `ACTIVE` list of definition keys, plus the three directory paths |
| `definitions/*.py` | One file per vendor |
| `invoices/*.pdf` | Drop invoice PDFs here |
| `run.bat` / `run.sh` | Double-click to run |

`config.py`, `definitions/`, `invoices/`, and `out/` are gitignored. The repo
ships `config.example.py` and an empty scaffold; your real config, vendor
parsers (which often carry private resource ids), PDFs, and output never get
committed.

## Architecture

- `cuenta/` — framework. Auto-discovers `definitions/*.py`, validates each
  (pydantic), extracts text with `pdftotext -layout`, routes each PDF to the one
  definition whose `detect` matches, runs its `parse`, reconciles, writes JSONL.
- `definitions/` — one file per vendor, each exposing a `definition = {...}` dict.
  Files starting with `_` are skipped by discovery but importable as modules (use
  them for shared helpers, e.g. a parser for a billing platform several vendors
  share).
- `config.py` — active keys and the directory paths.

Failures are isolated per PDF, so one unparseable invoice doesn't sink the batch.

## The Definition Contract

Each `definitions/*.py` defines a single top-level `definition` dict.

```python
from _acme import extract_header, iter_charges   # optional "_"-prefixed shared helper

def parse(text: str) -> dict:
    header = extract_header(text)
    ...
    return {
        "invoice_no": header.invoice_no,
        "date": header.date,            # ISO YYYY-MM-DD
        "total": header.total,          # grand total, for reconciliation
        "period": "May 2026",           # optional human label
        "lines": [                      # one or more buckets; must sum to total
            {"app": "web", "amount": 26.80, "note": "compute 9.44; database 17.36"},
            {"app": "worker", "amount": 12.90},
            {"app": "shared", "amount": 1.80},
        ],
    }

definition = {
    "key": "acme_cloud",             # snake_case; used in ACTIVE and the run summary
    "vendor": "Acme Cloud",          # stamped on every row
    "currency": "USD",               # optional, default "USD"
    "detect": "ACME-INV",            # str, list[str], or callable(text) -> bool
    "parse": parse,                  # callable(text) -> dict (validated below)
}
```

### Definition fields

| Field | Type | Notes |
|---|---|---|
| `key` | `str` (snake_case) | Used in `ACTIVE` and the run summary |
| `vendor` | `str` | Display name stamped on every emitted row |
| `detect` | `str` \| `list[str]` \| `callable` | How to recognize this vendor's PDF text. A string/list is a substring test; a callable takes the text and returns a bool |
| `parse` | `callable(text) -> dict` | Returns the parsed-invoice dict below |
| `currency` | `str` | Optional, default `"USD"` |

### Parse output

`parse` returns a dict validated against this shape (unknown keys rejected):

| Field | Type | Notes |
|---|---|---|
| `invoice_no` | `str` | |
| `date` | `str` | ISO `YYYY-MM-DD` |
| `total` | `float` | Invoice grand total; the per-app lines must reconcile to it |
| `lines` | `list` | One or more `{app, amount, note?}` buckets |
| `period` | `str` | Optional human label (e.g. `"May 2026"`) |

Each line: `app` (str, non-empty, e.g. an app slug or `"shared"`), `amount`
(float), optional `note` (str). The summed line amounts must equal `total`
within $0.02, or the invoice is reported as an error and no rows are written.

### Emitted rows

One JSONL object per line:

```json
{"date":"2026-05-31","vendor":"Acme Cloud","type":"expense","app":"web","amount":26.80,"currency":"USD","invoice_no":"ACME-2026-0042","period":"May 2026","note":"compute 9.44; database 17.36","source":"ACME-2026-0042.pdf"}
```

## config.py

```python
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

DEFINITIONS_DIR = REPO_ROOT / "definitions"
INVOICES_DIR    = REPO_ROOT / "invoices"
OUTPUT_DIR      = REPO_ROOT / "out"

ACTIVE: list[str] = [
    "acme_cloud",
]
```

## Errors and exit codes

Cuenta isolates failures so one bad PDF or definition doesn't stop the rest.

- **Load error** (broken Python file) — reported, file skipped, others continue.
- **Validation error** (bad definition contract) — reported, definition excluded.
- **No / multiple matches** — a PDF that no active `detect` matches, or more than
  one, is reported as an error for that file.
- **Parse / reconciliation error** — a parser that raises, returns an invalid
  shape, or whose line amounts don't sum to the invoice total is reported with a
  message; that file produces no rows, others continue.

| Exit code | Meaning |
|---|---|
| 0 | All PDFs parsed and reconciled cleanly |
| 1 | Ran, but at least one load / validation / parse / reconciliation error |
| 2 | Aborted before run (config invalid, definitions dir missing) |

## Non-goals

- **No fetching or auth.** Cuenta parses PDFs already on disk. Downloading them
  from a billing portal (often behind SSO) is out of scope; drop them in
  `invoices/` yourself.
- **No importing.** Output is JSONL. Loading it into your accounting system is a
  separate, deliberate step.
- **No guessing.** A charge that references an unknown resource fails loudly
  rather than being misfiled. Map the new resource in your definition and re-run.
