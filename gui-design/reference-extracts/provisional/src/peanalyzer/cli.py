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
    parser = argparse.ArgumentParser(prog="peanalyzer", description="Prime-editing metadata, demultiplexing and biological-sample statistics")
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
    for name in ("summarize", "stats"):
        command = commands.add_parser(name, help="aggregate biological samples" if name == "summarize" else "test explicit biological contrasts")
        for option in ("manifest", "samples", "output"):
            command.add_argument(f"--{option}", type=Path, required=True)
        if name == "stats":
            command.add_argument("--contrasts", type=Path, required=True)
            command.add_argument("--max-permutations", type=int, default=100_000)
    command = commands.add_parser("report", help="render a completed M5 result as an offline report")
    command.add_argument("--result", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    from peanalyzer.reporting_models import DEFAULT_TITLE, ReportingError
    command.add_argument("--title", default=DEFAULT_TITLE)
    for name in ("run", "analyze"):
        workflow = commands.add_parser(name, help="execute a validated local workflow from raw FASTQ" if name == "run" else "analyze an immutable verified demux archive")
        for option in ("samples", "targets", "config", "output"):
            workflow.add_argument("--" + option, type=Path, required=True)
        if name == "run":
            workflow.add_argument("--r1", type=Path, required=True)
            workflow.add_argument("--r2", type=Path, required=True)
        else:
            workflow.add_argument("--demux-root", type=Path, required=True)
        workflow.add_argument("--crispresso", required=True)
        workflow.add_argument("--runtime-digest", required=True)
        for option in ("barcodes", "contrasts", "tolerance-policies"):
            workflow.add_argument("--" + option, type=Path)
        workflow.add_argument("--title", default=DEFAULT_TITLE)
        workflow.add_argument("--analysis-r1-trim-5p", type=int)
        workflow.add_argument("--analysis-r2-trim-5p", type=int)
        workflow.add_argument("--resume", action="store_true")
        workflow.add_argument("--force", action="append", default=[], choices=["demux", "analysis", "routing", "metrics", "statistics", "report", "all"])
    args = parser.parse_args(argv)
    from peanalyzer.demux import DemuxError, demultiplex
    from peanalyzer.fastq import FastqError
    from peanalyzer.validation import load_config
    from peanalyzer.aggregation import AggregationError, summarize
    from peanalyzer.statistics import stats
    from peanalyzer.workflow_storage import WorkflowError
    try:
        if args.command in ("run", "analyze"):
            from peanalyzer.workflow import execute_workflow
            options = vars(args).copy()
            options["mode"] = options.pop("command")
            options["argv"] = ([str(Path(sys.argv[0]).resolve()), *sys.argv[1:]] if argv is None else [parser.prog, *argv])
            with sigterm_cleanup():
                report = execute_workflow(**options)
        elif args.command == "validate":
            report = validate_metadata(args.samples, args.targets, args.config, args.barcodes)
        elif args.command == "report":
            from peanalyzer.reporting import generate_report
            with sigterm_cleanup():
                manifest = generate_report(result_path=args.result, output=args.output, title=args.title)
            report = dict(output=str(args.output), report_contract_version=manifest.report_contract_version,
                          source_result_sha256=manifest.source_result_sha256, artifacts=len(manifest.artifacts))
        elif args.command in ("summarize", "stats"):
            options = dict(manifest_path=args.manifest, samples_path=args.samples, output=args.output)
            with sigterm_cleanup():
                result = summarize(**options) if args.command == "summarize" else stats(
                    **options, contrasts_path=args.contrasts, max_permutations=args.max_permutations)
            report = dict(output=str(args.output), observations=len(result.observations),
                          group_summaries=len(result.group_summaries), contrasts=len(result.contrasts),
                          statistics_contract_version=result.statistics_contract_version)
        else:
            logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
            with sigterm_cleanup():
                report = demultiplex(r1=args.r1, r2=args.r2, samples_path=args.samples,
                                     barcodes_path=args.barcodes, config=load_config(args.config), output=args.output,
                                     command_argv=([str(Path(sys.argv[0]).resolve()), *sys.argv[1:]] if argv is None
                                                   else [parser.prog, *argv]))
    except (MetadataError, FastqError, DemuxError, AggregationError, ReportingError, WorkflowError, OSError) as exc:
        label = {"validate": "Validation", "demux": "Demultiplexing", "summarize": "Summarization", "stats": "Statistics", "report": "Reporting", "run": "Workflow", "analyze": "Workflow"}[args.command]
        print(f"{label} failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0
