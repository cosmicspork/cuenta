"""Cuenta CLI entry point: load config, discover, validate, parse PDFs to JSONL."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from cuenta import __version__, loader, runner, validator
from cuenta.config import Config, ConfigError, load_config


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    print(f"cuenta {__version__}")
    try:
        cfg = load_config()
    except ConfigError as e:
        print(f"ERROR: {e}")
        return 2

    print(f"  definitions: {cfg.definitions_dir}")
    print(f"  invoices:    {cfg.invoices_dir}")
    print(f"  output:      {cfg.output_dir}")
    print(f"  active:      {cfg.active or '(none)'}")
    print()

    if not cfg.definitions_dir.is_dir():
        print(f"ERROR: definitions directory not found: {cfg.definitions_dir}")
        return 2

    return _run(cfg, args)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="cuenta")
    p.add_argument(
        "pdfs",
        nargs="*",
        type=Path,
        help="Specific PDF(s) to parse. Default: every *.pdf in INVOICES_DIR.",
    )
    p.add_argument(
        "--only",
        default=None,
        help="Comma-separated subset of ACTIVE keys to route against.",
    )
    return p.parse_args(argv)


def _run(cfg: Config, args: argparse.Namespace) -> int:
    loaded, load_errors = loader.discover(cfg.definitions_dir)
    for le in load_errors:
        print(f"[load] {le.source_path.name}: {le.message}")

    valid, validation_errors = validator.validate_all(loaded, cfg.active)
    for ve in validation_errors:
        print(f"[validate] {ve}")
    had_errors = bool(load_errors or validation_errors)

    only = {p.strip() for p in args.only.split(",") if p.strip()} if args.only else None
    if only is not None:
        for k in sorted(only - set(cfg.active)):
            print(f"[--only] {k!r} is not in ACTIVE; ignored.")
        active_keys = [k for k in cfg.active if k in only]
    else:
        active_keys = list(cfg.active)

    active_defs = [v for v in valid if v.key in active_keys]
    print(f"\nFound {len(loaded)} definition(s); {len(valid)} valid; {len(active_defs)} active.")
    if not active_defs:
        print("Nothing to route against.")
        return 1 if had_errors else 0

    pdfs = _gather_pdfs(cfg, args)
    if not pdfs:
        print("No PDFs to parse.")
        return 1 if had_errors else 0

    out_path = cfg.output_dir / f"{datetime.now().strftime('%Y-%m-%d_%H%M')}.jsonl"
    print(f"Parsing {len(pdfs)} PDF(s) -> {out_path}\n")
    results = runner.run_all(pdfs, active_defs, out_path)
    _print_summary(results)

    any_error = had_errors or any(r.status == "error" for r in results)
    return 1 if any_error else 0


def _gather_pdfs(cfg: Config, args: argparse.Namespace) -> list[Path]:
    if args.pdfs:
        return [p for p in args.pdfs if p.is_file()]
    if not cfg.invoices_dir.is_dir():
        print(f"ERROR: invoices directory not found: {cfg.invoices_dir}")
        return []
    return sorted(cfg.invoices_dir.glob("*.pdf"))


def _print_summary(results: list[runner.RunResult]) -> None:
    print("Results:")
    total_rows = 0
    for r in results:
        if r.status == "ok":
            total_rows += r.rows
            print(f"  ok    [{r.source}] {r.vendor} {r.invoice_no} -> {r.rows} row(s), ${r.total}")
        else:
            print(f"  ERROR [{r.source}] {r.message}")
    print(f"\n{total_rows} row(s) written.")


if __name__ == "__main__":
    sys.exit(main())
