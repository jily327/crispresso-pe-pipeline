"""Command-line boundary, kept separate from reusable validation functions."""

import argparse
import json
import sys
from pathlib import Path

from peanalyzer import __version__
from peanalyzer.validation import MetadataError, validate_metadata


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="peanalyzer", description="Prime-editing pipeline: Milestone 1 metadata validation")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="validate metadata without running sequence analysis")
    validate.add_argument("--samples", type=Path, required=True)
    validate.add_argument("--targets", type=Path, required=True)
    validate.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = validate_metadata(args.samples, args.targets, args.config)
    except MetadataError as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0
