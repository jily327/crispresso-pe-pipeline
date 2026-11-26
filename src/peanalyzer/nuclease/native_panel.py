"""Original Core multi-WT run on the complete prepared sample, before classification."""
import json
import shutil
import subprocess

from peanalyzer.backend.comparator import normalize_include_idxs
from peanalyzer.backend.native_artifacts import extract_native
from peanalyzer.backend.pooled import utc_now
from peanalyzer.demux_verify import sha256_file
from peanalyzer.nuclease.qualification import scientific_arguments, validate_arguments


def run_native_panel(stage, verified, sample_id, targets, core, runtime_digest):
    stage.mkdir()
    sample = verified.manifest['samples'][sample_id]
    names = [target.copy_name for target in targets]
    sequences = [target.wt_sequence for target in targets]
    windows = [target.window['coordinates'] for target in targets]
    execution = dict(analysis_mode='native_multi_wt_nuclease', sample_id=sample_id, target_name=targets[0].target_name,
                     runtime_digest=runtime_digest, version_probe=core.probe, started_at=utc_now(),
                     input_pairs=sample['pairs'], reference_names=names, reference_sequences=sequences, windows=windows)
    for mate in (1,2):
        entry = sample['files'][f'r{mate}']
        dest = stage/f'input_R{mate}.fastq.gz'
        shutil.copyfile(verified.root/entry['path'],dest)
        if sha256_file(dest) != entry['sha256']:
            raise ValueError('NATIVE_NUCLEASE_PREPARED_INPUT_CHANGED')

    def save():
        (stage/'execution.json').write_text(json.dumps(execution,indent=2,sort_keys=True)+'\n')

    seq_arg, name_arg, win_arg = ','.join(sequences), ','.join(names), ','.join(windows)
    argv = [core.path,'-r1','input_R1.fastq.gz','-r2','input_R2.fastq.gz','--amplicon_seq',seq_arg,
            '--amplicon_name',name_arg,'--quantification_window_coordinates',win_arg,
            '--exclude_bp_from_left','0','--exclude_bp_from_right','0','--name','multi_wt','--output_folder','output',
            '--write_detailed_allele_table','--keep_intermediate']
    execution.update(argv=argv,cwd=str(stage),status='running')
    save()
    with (stage/'stdout.txt').open('w') as out, (stage/'stderr.txt').open('w') as err:
        code = subprocess.run(argv,cwd=stage,stdout=out,stderr=err,check=False).returncode
    execution.update(return_code=code,ended_at=utc_now(),status='failed' if code else 'completed')
    if code:
        execution['reason_code'] = 'NATIVE_MULTI_WT_COMMAND_FAILED'
        save()
        return
    child = stage/'output/CRISPResso_on_multi_wt'
    info = json.loads((child/'CRISPResso2_info.json').read_text())
    running, results = info['running_info'], info['results']
    if running['version'] != '2.3.4' or not running.get('end_time_string') or results['ref_names'] != names:
        raise ValueError('NATIVE_NUCLEASE_RUN_IDENTITY_MISMATCH')
    args = running['args']['value']
    validate_arguments(args,dict(scientific_arguments(seq_arg,win_arg),amplicon_name=name_arg))
    if (args['fastq_r1'],args['fastq_r2']) != ('input_R1.fastq.gz','input_R2.fastq.gz'):
        raise ValueError('NATIVE_NUCLEASE_MATE_ORDER_MISMATCH')
    for target in targets:
        ref = results['refs'][target.copy_name]
        positions = [p for a,b in target.window['intervals'] for p in range(a,b+1)]
        if ref['sequence'] != target.wt_sequence or normalize_include_idxs(ref['include_idxs'],len(target.wt_sequence)) != positions:
            raise ValueError('NATIVE_NUCLEASE_EFFECTIVE_WINDOW_MISMATCH')
    observed = extract_native(child/'CRISPResso2_info.json')
    if observed['counts']['backend_input_reads'] != sample['pairs']:
        raise ValueError('NATIVE_NUCLEASE_INPUT_COUNT_MISMATCH')
    execution['resolved_backend_arguments'] = args
    save()
