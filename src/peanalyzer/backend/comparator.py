"""Qualification-only conventional Core comparator on ALL prepared pairs.

This is not a production sample report, routing bypass, or copy-level metric.
Empirical integer anchor invariance is mandatory; preflight is only necessary.
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from peanalyzer.analysis_verify import verify_analysis_output
from peanalyzer.backend.metrics import parse_child, backend_failure_code
from peanalyzer.backend.pooled import FIELDS, BackendError, utc_now
from peanalyzer.demux_verify import sha256_file, read_json
from peanalyzer.geometry import geometry
from peanalyzer.provenance import software_provenance


COMPARISON_FIELDS=('backend_input_reads','reads_after_preprocessing','preprocessing_count_delta',
                   'aligned_reads','unaligned_reads','numerator','denominator')


def normalize_include_idxs(value, reference_length):
    """Validate list or CRISPResso2's JSON ndarray encoding; fail closed."""
    if isinstance(value,dict):
        if set(value)!={'_type','value'} or value['_type']!='np.ndarray':
            raise ValueError('unknown authoritative include_idxs serialization')
        value=value['value']
    if not isinstance(value,list) or any(type(p) is not int or not 0<=p<reference_length for p in value):
        raise ValueError('authoritative include_idxs must be a one-dimensional list of valid integer positions')
    return sorted(set(value))


def evaluate_anchors(targets, metrics):
    report=geometry(targets)
    reasons=[]
    copies={t.copy_name for t in targets}
    if set(metrics)!=copies or not copies:
        reasons.append('MISSING_ANCHOR_RESULT')
    # For this qualified representation copies share WT coordinates (no copy indels).
    if any(r['code'] in ('COPY_INDEL_ROUTING_UNQUALIFIED','NONUNIQUE_REFERENCE_ALIGNMENT','NONUNIQUE_EDIT_ALIGNMENT') for r in report['reasons']):
        reasons.append('EDIT_COORDINATES_NOT_COMPARABLE')
    signatures={tuple((e['wt_position'],e.get('wt_boundary'),e['old'],e['new']) for e in report['copies'][c]['edits']) for c in copies}
    if len(signatures)!=1:
        reasons.append('INTENDED_EDIT_STATE_DIFFERS_BETWEEN_COPIES')
    values={c:{k:m['native'][k] for k in COMPARISON_FIELDS} for c,m in metrics.items()}
    invariant=bool(values) and len({tuple(v[k] for k in COMPARISON_FIELDS) for v in values.values()})==1 and set(metrics)==copies
    if set(metrics)==copies and not invariant: reasons.append('ANCHOR_DEPENDENT_NATIVE_RESULT')
    overlap={};normalized_windows={}
    lengths={t.copy_name:len(t.wt_sequence) for t in targets}
    for c,m in metrics.items():
        if c not in copies: continue
        window=m.get('authoritative_reference_quantification_window')
        if window is None:
            reasons.append('AUTHORITATIVE_QUANTIFICATION_WINDOW_MISSING')
            continue
        try:
            window=normalize_include_idxs(window,lengths[c])
        except ValueError:
            reasons.append('AUTHORITATIVE_QUANTIFICATION_WINDOW_INVALID')
            continue
        normalized_windows[c]=window
        overlap[c]=[d['positions'][c] for d in report['diagnostics'] if d['positions'][c] in window]
        if overlap[c]: reasons.append('DIAGNOSTIC_IN_AUTHORITATIVE_QUANTIFICATION_WINDOW')
    return dict(scope='qualification_only_all_prepared_pairs_not_confident_copy_cohort',
                metric='target_crispresso_native_pe',status='BLOCKED' if reasons else 'SUPPORTED_IN_TESTED_FIXTURE',
                reasons=sorted(set(reasons)),anchor_invariant=invariant,anchors=values,
                authoritative_window_diagnostics=overlap,
                authoritative_windows=normalized_windows,
                limitation='Necessary eligibility checks and empirical invariance on this input do not qualify unseen targets or data.')


def run_comparator(analysis_root, sample_id, targets, output, core, *, runtime_identity=None):
    """Run each valid anchor independently, preserving actual backend artifacts."""
    if core.version!='2.3.4': raise BackendError('VERSION_MISMATCH','requires 2.3.4')
    verified=verify_analysis_output(Path(analysis_root))
    sample=verified.manifest['samples'][sample_id]
    output=Path(output).absolute()
    if output.exists(): raise ValueError('comparator output must be new')
    output.mkdir(parents=True)
    metrics={}; failures={}
    for target in sorted(targets,key=lambda t:t.copy_name):
        with tempfile.TemporaryDirectory(prefix='m311-comparator-') as temporary:
            work=Path(temporary)
            for mate in (1,2):
                entry=sample['files'][f'r{mate}']
                dest=work/f'input_R{mate}.fastq.gz'
                shutil.copyfile(verified.root/entry['path'],dest)
                if sha256_file(dest)!=entry['sha256']: raise ValueError('analysis input changed')
            argv=[core.path,'-r1','input_R1.fastq.gz','-r2','input_R2.fastq.gz',
                  '--amplicon_seq',target.wt_sequence,'--name','unrouted','--output_folder','output',
                  '--write_detailed_allele_table','--keep_intermediate','--suppress_report','--suppress_plots']
            for column,field in list(FIELDS.items())[2:]:
                value=getattr(target,field)
                if value is not None: argv.extend(['--'+column,str(value)])
            execution=dict(scope='qualification_only_unrouted_all_prepared_reads',argv=argv,
                           started_at=utc_now(),runtime_identity=runtime_identity,software=software_provenance(),
                           analysis_manifest_sha256=verified.manifest_sha256,inputs=sample,status='running',return_code=None)
            try:
                with (work/'stdout.txt').open('w') as out,(work/'stderr.txt').open('w') as err:
                    try:
                        run=subprocess.run(argv,cwd=work,stdout=out,stderr=err,check=False)
                    except OSError as exc:
                        raise BackendError('COMMAND_FAILED', str(exc)) from exc
                execution['return_code']=run.returncode
                if run.returncode: raise BackendError('COMMAND_FAILED',f'comparator Core exit {run.returncode}')
                child=work/'output/CRISPResso_on_unrouted'
                refs=read_json(child/'CRISPResso2_info.json')['results']['refs']
                if refs['Reference']['sequence']!=target.wt_sequence or refs['Prime-edited']['sequence']!=target.prime_edited_sequence:
                    raise BackendError('BACKEND_REFERENCE_MISMATCH','comparator reference mismatch')
                metrics[target.copy_name]=parse_child(child,routed_pairs=sample['pairs'],one_input_record_per_pair=True,
                                                      preprocessing_preserves_records=False)
                execution['status']='completed'
            except Exception as exc:
                code=backend_failure_code(exc)
                failures[target.copy_name]=code
                execution.update(status='failed',error=str(exc),reason_code=code)
            finally:
                execution['ended_at']=utc_now()
                (work/'execution.json').write_text(json.dumps(execution,indent=2)+'\n')
                shutil.copytree(work,output/target.copy_name)
    result=evaluate_anchors(targets,metrics)
    if failures:
        result['reasons']=sorted((set(result['reasons'])-{'MISSING_ANCHOR_RESULT'}) | set(failures.values()))
    result['anchor_failures']=failures
    result['backend_metrics']=metrics
    (output/'comparator.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
