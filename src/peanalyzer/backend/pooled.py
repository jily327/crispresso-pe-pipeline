"""Pinned executable boundary and Pooled TSV generation, not editing metrics."""

import csv
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from peanalyzer.demux_verify import read_json, sha256_file
from peanalyzer.provenance import software_provenance
from peanalyzer.schemas import Target, reverse_complement

VERSION = "2.3.4"
FIELDS = {
    "amplicon_name": "amplicon_id", "amplicon_seq": "wt_sequence",
    "prime_editing_pegRNA_spacer_seq": "pegRNA_spacer",
    "prime_editing_nicking_guide_seq": "nicking_guide",
    "prime_editing_pegRNA_extension_seq": "pegRNA_extension",
    "prime_editing_pegRNA_scaffold_seq": "pegRNA_scaffold",
    "prime_editing_override_prime_edited_ref_seq": "prime_edited_sequence",
    "prime_editing_pegRNA_scaffold_min_match_length": "prime_editing_pegRNA_scaffold_min_match_length",
    "quantification_window_coordinates": "quantification_window_coordinates",
    "quantification_window_size": "quantification_window_size",
    "quantification_window_center": "quantification_window_center",
}


class BackendError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Executable:
    path: str
    version: str
    probe: dict


def resolve_executable(command: str, required_version: str = VERSION) -> Executable:
    path = shutil.which(command)
    if path is None:
        raise BackendError("EXECUTABLE_MISSING", command)
    path = str(Path(path).resolve())
    argv, start = [path, "--version"], utc_now()
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise BackendError("VERSION_PROBE_FAILED", str(exc)) from exc
    text = result.stdout + result.stderr
    match = re.search(r"\bCRISPResso(?:Pooled)?\s+(\d+\.\d+\.\d+)\b", text)
    if result.returncode or not match or match[1] != required_version:
        raise BackendError("VERSION_MISMATCH", f"required {required_version}; observed {text.strip()!r}")
    return Executable(path, match[1], {"argv": argv, "started_at": start, "ended_at": utc_now(),
                                     "return_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr})


def validate_targets(targets: list[Target]) -> None:
    if not targets or len({t.amplicon_id.casefold() for t in targets}) != len(targets):
        raise BackendError("MALFORMED_AMPLICON_INPUT", "empty or colliding target/copy identifiers")
    seen = set()
    for target in targets:
        wt = target.wt_sequence
        if wt in seen or reverse_complement(wt) in seen or wt == reverse_complement(wt):
            raise BackendError("MALFORMED_AMPLICON_INPUT", "WT references must be distinct, including reverse complements")
        seen.add(wt)
        if reverse_complement(target.pegRNA_extension) not in target.prime_edited_sequence:
            raise BackendError("PE_EXTENSION_REFERENCE_INCOMPATIBLE", target.amplicon_id)


def preflight_guides(targets: list[Target]) -> None:
    """Represent the empirically confirmed 2.3.4 exact-spacer limitation."""
    for target in targets:
        if target.pegRNA_spacer not in target.wt_sequence and reverse_complement(target.pegRNA_spacer) not in target.wt_sequence:
            raise BackendError("PE_GUIDE_REFERENCE_MISMATCH_UNSUPPORTED",
                               f"{target.amplicon_id}: actual experimental spacer is absent from WT in both orientations; "
                               "CRISPResso2 2.3.4 rejects this configuration")


def write_amplicons(path: Path, targets: list[Target]) -> None:
    validate_targets(targets)
    with Path(path).open("x", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(FIELDS)
        for target in sorted(targets, key=lambda row: row.amplicon_id):
            writer.writerow("NA" if getattr(target, field) is None else getattr(target, field) for field in FIELDS.values())


def pooled_argv(executable: str, *, child_core_command: str = "CRISPResso", min_reads: int = 0,
                diagnostic_intermediates: bool = True) -> list[str]:
    if type(min_reads) is not int or min_reads < 0:
        raise BackendError("INVALID_CONFIGURATION", "min_reads must be a nonnegative integer")
    argv = [executable, "-r1", "input_R1.fastq.gz", "-r2", "input_R2.fastq.gz", "-f", "amplicons.tsv",
            "-o", "output", "--name", "diagnostic", "--crispresso_command", shlex.quote(child_core_command),
            "--n_processes", "1", "--min_reads_to_use_region", str(min_reads), "--write_detailed_allele_table",
            "--suppress_report", "--suppress_plots"]
    if diagnostic_intermediates:
        argv.append("--keep_intermediate")
    return argv


def check_pooled_output(root: Path) -> dict:
    path = root / "output/CRISPRessoPooled_on_diagnostic/CRISPResso2Pooled_info.json"
    if not path.is_file():
        raise BackendError("MISSING_ARTIFACT", str(path.relative_to(root)))
    try:
        data = read_json(path)
        if data["running_info"]["version"] != VERSION or not data["running_info"].get("end_time_string"):
            raise ValueError("wrong version or missing completion timestamp")
        if data["results"].get("failed_batch_arr"):
            raise BackendError("CHILD_ANALYSIS_FAILED", str(data["results"]["failed_batch_arr"]))
        return data
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise BackendError("INVALID_ARTIFACT", str(exc)) from exc


def run_pooled_diagnostic(*, r1: Path, r2: Path, targets: list[Target], output: Path,
                          pooled: Executable, core: Executable, child_core_command: str | None = None,
                          min_reads: int = 0, diagnostic_intermediates: bool = True,
                          diagnostic_test_unsupported_guide: bool = False) -> dict:
    """Stage safe relative paths because Pooled internally invokes shell tools.

    API calls subprocess with argv and shell=False. Output is a diagnostic run,
    not authorization for copy-specific downstream quantification.
    """
    validate_targets(targets)
    if not diagnostic_test_unsupported_guide:
        preflight_guides(targets)
    if pooled.version != VERSION or core.version != VERSION:
        raise BackendError("VERSION_MISMATCH", "both Core and Pooled must be 2.3.4")
    r1, r2, output = Path(r1).resolve(), Path(r2).resolve(), Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise BackendError("OUTPUT_EXISTS", str(output))
    sources = {"r1": {"path": str(r1), "sha256": sha256_file(r1)}, "r2": {"path": str(r2), "sha256": sha256_file(r2)}}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="peanalyzer-backend-") as temporary:
        work = Path(temporary)
        if not re.fullmatch(r"[/A-Za-z0-9_.-]+", str(work)):
            raise BackendError("UNSAFE_SCRATCH_PATH", "set TMPDIR to a path without shell metacharacters or spaces")
        for source, name in ((r1, "input_R1.fastq.gz"), (r2, "input_R2.fastq.gz")):
            shutil.copyfile(source, work / name)
        for mate in (1, 2):
            if sha256_file(work / f"input_R{mate}.fastq.gz") != sources[f"r{mate}"]["sha256"]:
                raise BackendError("INPUT_CHANGED", "FASTQ changed during staging")
        write_amplicons(work / "amplicons.tsv", targets)
        argv = pooled_argv(pooled.path, child_core_command=child_core_command or core.path,
                           min_reads=min_reads, diagnostic_intermediates=diagnostic_intermediates)
        manifest = {"schema_version": 1, "status": "running", "scope": "backend_diagnostic_only", "software": software_provenance(),
                    "core_version": core.version, "pooled_version": pooled.version, "version_probes": [core.probe, pooled.probe],
                    "executable_path": pooled.path, "argv": argv, "cwd": str(work), "output_path": str(output), "inputs": sources,
                    "amplicons_sha256": sha256_file(work / "amplicons.tsv"),
                    "target_configuration_sha256": hashlib.sha256(json.dumps([t.model_dump() for t in sorted(targets, key=lambda t: t.amplicon_id)], sort_keys=True).encode()).hexdigest(),
                    "diagnostic_test_unsupported_guide": diagnostic_test_unsupported_guide,
                    "started_at": utc_now(), "return_code": None}
        error = None
        try:
            with (work / "stdout.log").open("w") as stdout, (work / "stderr.log").open("w") as stderr:
                result = subprocess.run(argv, cwd=work, stdout=stdout, stderr=stderr, check=False)
            manifest["return_code"] = result.returncode
            if result.returncode:
                if "The given prime editing pegRNA spacer is not found in the reference sequence" in (work / "stderr.log").read_text():
                    raise BackendError("PE_GUIDE_REFERENCE_MISMATCH_UNSUPPORTED", f"backend exit {result.returncode}; see stderr.log")
                raise BackendError("COMMAND_FAILED", f"exit {result.returncode}; see stderr.log")
            check_pooled_output(work)
            manifest["status"] = "completed"
        except (OSError, BackendError) as exc:
            error = exc if isinstance(exc, BackendError) else BackendError("EXECUTION_FAILED", str(exc))
            manifest.update(status="failed", error_code=error.code, error=str(error))
        finally:
            manifest["ended_at"] = utc_now()
            (work / "execution.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.incomplete-", dir=output.parent))
            try:
                shutil.copytree(work, stage, dirs_exist_ok=True)
                if output.exists():
                    raise BackendError("OUTPUT_EXISTS", str(output))
                stage.rename(output)
            finally:
                if stage.exists():
                    shutil.rmtree(stage)
        if error:
            raise error
        return manifest
