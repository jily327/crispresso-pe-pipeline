"""Prepare separate analysis inputs only after verifying the archived M2 run."""

import gzip
import json
import shutil
import tempfile
from pathlib import Path

from peanalyzer.demux_verify import sha256_file, verify_demux_output
from peanalyzer.fastq import paired_fastq
from peanalyzer.schemas import Model, NonnegativeInt


class PreparationError(ValueError):
    pass


class PreparationConfig(Model):
    r1_analysis_trim_5p: NonnegativeInt | None = None
    r2_analysis_trim_5p: NonnegativeInt | None = None


def resolve_trims(summary: dict, config: PreparationConfig) -> tuple[int, int]:
    supplied = (config.r1_analysis_trim_5p, config.r2_analysis_trim_5p)
    if any(n is not None for n in supplied):
        if any(n is None for n in supplied):
            raise PreparationError("supply both analysis trim sizes")
        return supplied
    settings = summary["resolved_config"]["demux"]
    if settings["profile"] != "qi_hitom_v1" or settings["trim_barcodes"] or settings["trim_bridges"]:
        raise PreparationError("automatic preparation requires untrimmed qi_hitom_v1 archives; specify explicit trim sizes for other layouts")
    trims = []
    for direction in ("forward", "reverse"):
        rule = summary["extraction_profile"]["rules"][direction]
        length = summary["barcode_catalog"]["matching_safety"][direction]["barcode_length"]
        if type(rule["start"]) is not int or rule["start"] < 0 or type(length) is not int or length < 1 or not rule["bridge"]:
            raise PreparationError("invalid recorded extraction layout")
        trims.append(rule["start"] + length + len(rule["bridge"]))
    return tuple(trims)


def prepare_analysis_fastqs(demux_root: Path, output: Path, config: PreparationConfig | None = None) -> dict:
    verified = verify_demux_output(demux_root)
    output = Path(output).absolute()
    if output.exists() or output.is_symlink() or output.resolve().is_relative_to(verified.root):
        raise PreparationError("analysis output must be new and separate from the immutable M2 run")
    trims = resolve_trims(verified.summary, config or PreparationConfig())
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.incomplete-", dir=output.parent))
    try:
        directory = staging / "03_analysis_fastq"
        directory.mkdir()
        samples = {}
        for sample in verified.samples:
            paths = [directory / f"{sample.sample_id}_R{mate}.analysis.fastq.gz" for mate in (1, 2)]
            count = 0
            with paths[0].open("xb") as raw1, paths[1].open("xb") as raw2:
                with gzip.GzipFile(filename="", fileobj=raw1, mode="wb", mtime=0) as out1, gzip.GzipFile(filename="", fileobj=raw2, mode="wb", mtime=0) as out2:
                    for pair in paired_fastq(sample.r1, sample.r2):
                        for record, trim, handle in zip(pair, trims, (out1, out2)):
                            # Equality would produce an invalid empty FASTQ read.
                            if len(record.sequence) <= trim:
                                raise PreparationError(f"sample {sample.sample_id}: read length must exceed trim {trim}")
                            handle.write(record.trimmed(trim).to_bytes())
                        count += 1
            if count != sample.pairs or sum(1 for _ in paired_fastq(*paths)) != sample.pairs:
                raise PreparationError(f"prepared pair count mismatch: {sample.sample_id}")
            for path, expected in ((sample.r1, sample.r1_sha256), (sample.r2, sample.r2_sha256)):
                if sha256_file(path) != expected:
                    raise PreparationError("source demux file changed during preparation")
            samples[sample.sample_id] = {"pairs": count, "files": {
                f"r{mate}": {"path": path.relative_to(staging).as_posix(), "sha256": sha256_file(path), "size_bytes": path.stat().st_size}
                for mate, path in enumerate(paths, 1)}}
        if sha256_file(verified.root / "01_demux_QC/demux_summary.json") != verified.summary_sha256:
            raise PreparationError("source demux summary changed during preparation")
        manifest = {"schema_version": 1, "status": "completed", "verified_demux_root": str(verified.root),
                    "demux_summary_sha256": verified.summary_sha256,
                    "r1_analysis_trim_5p": trims[0], "r2_analysis_trim_5p": trims[1], "samples": samples}
        (staging / "analysis_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        if output.exists():
            raise PreparationError("analysis destination appeared during preparation")
        staging.rename(output)
        return manifest
    finally:
        if staging.exists():
            shutil.rmtree(staging)
