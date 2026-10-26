"""Verify prepared inputs against their immutable M2 source before consumption."""

from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path

from peanalyzer.analysis_fastq import PreparationConfig
from peanalyzer.demux_verify import read_json, sha256_file, verify_demux_output
from peanalyzer.fastq import paired_fastq


class AnalysisVerificationError(ValueError):
    pass


@dataclass(frozen=True)
class VerifiedAnalysisRun:
    root: Path
    manifest_sha256: str
    manifest: dict


def verify_analysis_output(path: Path) -> VerifiedAnalysisRun:
    try:
        supplied = Path(path)
        root = supplied.resolve(strict=True)
        if supplied.is_symlink() or any('.incomplete-' in p for p in (*supplied.parts, *root.parts)):
            raise ValueError('staging/symlink analysis root')
        manifest_path = root / 'analysis_manifest.json'
        before = sha256_file(manifest_path)
        data = read_json(manifest_path)
        if type(data['schema_version']) is not int or data['schema_version'] != 1 or data['status'] != 'completed':
            raise ValueError('unsupported/incomplete analysis manifest')
        config = PreparationConfig(r1_analysis_trim_5p=data['r1_analysis_trim_5p'], r2_analysis_trim_5p=data['r2_analysis_trim_5p'])
        trims = config.r1_analysis_trim_5p, config.r2_analysis_trim_5p
        if None in trims:
            raise ValueError('resolved trims required')
        source = verify_demux_output(Path(data['verified_demux_root']))
        if data['demux_summary_sha256'] != source.summary_sha256:
            raise ValueError('source M2 identity changed')
        if set(data['samples']) != {s.sample_id for s in source.samples}:
            raise ValueError('sample inventory mismatch')
        expected = set()
        for sample in source.samples:
            row = data['samples'][sample.sample_id]
            if type(row['pairs']) is not int or row['pairs'] != sample.pairs or set(row['files']) != {'r1', 'r2'}:
                raise ValueError('source/prepared count or mate inventory mismatch')
            paths = []
            for mate in (1, 2):
                relative = f'03_analysis_fastq/{sample.sample_id}_R{mate}.analysis.fastq.gz'
                item = row['files'][f'r{mate}']
                file = root / relative
                if item['path'] != relative or any(p.is_symlink() for p in (file, file.parent, manifest_path)):
                    raise ValueError('unexpected path/symlink')
                if type(item['size_bytes']) is not int or file.stat().st_size != item['size_bytes'] or sha256_file(file) != item['sha256']:
                    raise ValueError('prepared size/hash mismatch')
                paths.append(file)
                expected.add(file.name)
            count = 0
            for original, prepared in zip_longest(paired_fastq(sample.r1, sample.r2), paired_fastq(*paths)):
                if original is None or prepared is None:
                    raise ValueError('prepared/source record count mismatch')
                if any(a.trimmed(n).to_bytes() != b.to_bytes() for a, b, n in zip(original, prepared, trims)):
                    raise ValueError('prepared record differs from configured source trimming')
                count += 1
            if count != sample.pairs:
                raise ValueError('independent prepared recount mismatch')
        if {p.name for p in (root/'03_analysis_fastq').iterdir()} != expected:
            raise ValueError('extra/missing prepared file')
        if sha256_file(manifest_path) != before:
            raise ValueError('manifest changed during verification')
        return VerifiedAnalysisRun(root, before, data)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise AnalysisVerificationError(str(exc)) from exc
