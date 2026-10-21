"""Command-line boundary, kept separate from reusable validation functions."""

import argparse
import json
import logging
import signal
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

from peanalyzer import __version__
from peanalyzer.validation import MetadataError, validate_metadata


@contextmanager
def sigterm_cleanup():
    """CLI cancellation unwinds demux staging; API callers own their signals."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    def terminate(signum, frame):
        raise SystemExit(128 + signum)
    previous = signal.signal(signal.SIGTERM, terminate)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="peanalyzer", description="Prime-editing metadata validation and paired barcode demultiplexing")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="validate metadata without running sequence analysis")
    validate.add_argument("--samples", type=Path, required=True)
    validate.add_argument("--targets", type=Path, required=True)
    validate.add_argument("--config", type=Path, required=True)
    validate.add_argument("--barcodes", type=Path, help="catalog for ID-based full metadata")
    demux = commands.add_parser("demux", help="stream paired FASTQ into expected samples and barcode QC")
    for name in ("r1", "r2", "samples", "config", "output"):
        demux.add_argument(f"--{name}", type=Path, required=True)
    demux.add_argument("--barcodes", type=Path, help="custom CSV catalog; defaults to bundled catalog for qi_hitom_v1")
    args = parser.parse_args(argv)
    from peanalyzer.demux import DemuxError, demultiplex
    from peanalyzer.fastq import FastqError
    from peanalyzer.validation import load_config
    try:
        if args.command == "validate":
            report = validate_metadata(args.samples, args.targets, args.config, args.barcodes)
        else:
            logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
            with sigterm_cleanup():
                report = demultiplex(r1=args.r1, r2=args.r2, samples_path=args.samples,
                                     barcodes_path=args.barcodes, config=load_config(args.config), output=args.output,
                                     command_argv=([str(Path(sys.argv[0]).resolve()), *sys.argv[1:]] if argv is None
                                                   else [parser.prog, *argv]))
    except (MetadataError, FastqError, DemuxError, OSError) as exc:
        label = "Validation" if args.command == "validate" else "Demultiplexing"
        print(f"{label} failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0
