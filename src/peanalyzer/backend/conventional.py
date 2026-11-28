"""Conventional multi-WT Core run on original-order, complete prepared pairs."""
import json
import shutil
import subprocess
from pathlib import Path

from peanalyzer.backend.pooled import BackendError, utc_now
from peanalyzer.demux_verify import sha256_file
from peanalyzer.docker_runtime import IMAGE
from peanalyzer.schemas import reverse_complement


def run_conventional_panel(verified, sample_id, targets, core, runtime_digest, output):
    sample = verified.manifest['samples'][sample_id]
    if not sample['pairs'] or core.version != '2.3.4' or runtime_digest != IMAGE:
        raise ValueError('Nonempty verified prepared sample and qualified runtime required')
    work = Path(output)
    work.mkdir()
    seqs = [t.wt_sequence for t in targets]
    names = [t.copy_name for t in targets]
    ex = dict(analysis_mode='guide_free_multi_reference', version_probe=core.probe, runtime_digest=IMAGE,
              inputs=sample, started_at=utc_now(), status='not_started', return_code=None)
    windows = [t.quantification_window_coordinates or '0' for t in targets]
    try:
        if len({min(s, reverse_complement(s)) for s in seqs}) != len(seqs):
            ex['reason_code'] = 'INDISTINGUISHABLE_NATIVE_WT_REFERENCES'
            return
        args = [core.path, '-r1','input_R1.fastq.gz','-r2','input_R2.fastq.gz','--amplicon_seq',','.join(seqs),
                '--amplicon_name',','.join(names),'--name','multi_wt','--output_folder','output',
                '--write_detailed_allele_table','--keep_intermediate']
        # Guide-relative PE windows do not define guide-free windows. Explicitly
        # preserve Core's conventional defaults when supplied coordinates are absent.
        if any(w != '0' for w in windows):
            args += ['--quantification_window_coordinates',','.join(windows)]
        ex.update(argv=args, window_definition='supplied_WT_coordinates_or_Core_guide_free_default')
        for n in (1,2):
            entry = sample['files'][f'r{n}']
            dest = work/f'input_R{n}.fastq.gz'
            shutil.copyfile(verified.root/entry['path'], dest)
            if sha256_file(dest) != entry['sha256']:
                raise ValueError('Prepared input changed before conventional multi-reference run')
        with (work/'stdout.txt').open('w') as stdout, (work/'stderr.txt').open('w') as stderr:
            proc = subprocess.run(args, cwd=work, stdout=stdout, stderr=stderr)
        ex.update(status='failed' if proc.returncode else 'completed', return_code=proc.returncode)
        if proc.returncode:
            raise BackendError('COMMAND_FAILED', f'Conventional multi-reference Core exited with {proc.returncode}')
        native = json.loads((work/'output/CRISPResso_on_multi_wt/CRISPResso2_info.json').read_text())['results']
        if native['ref_names'] != names or [native['refs'][r]['sequence'] for r in names] != seqs:
            raise ValueError('Conventional multi-reference native inventory changed')
    finally:
        ex['ended_at'] = utc_now()
        (work/'execution.json').write_text(json.dumps(ex,indent=2)+'\n')
