"""Focused M4.1 overlap, runtime scope, partition and independent-anchor tests."""

import csv
import io
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from peanalyzer.backend.comparator import COMPARISON_FIELDS, evaluate_anchors
from peanalyzer.backend.metrics import MIN_EXACT_PAIR_OVERLAP, exact_pair_class, parse_child, MetricContractError
from peanalyzer.backend.pooled import Executable
from peanalyzer.metrics import MetricResult, run_metrics
from peanalyzer.metrics.production import RUNTIME_DIGEST
from peanalyzer.remediation import panel, pair
from peanalyzer.schemas import Target, reverse_complement
from test_m4 import archive, collect, mutate_info, write_json
from test_m312 import metrics_with_window


def overlap_cases():
    target = panel()[0]
    wt, pe = target.wt_sequence, target.prime_edited_sequence
    yield 'zero_overlap_insertion', target, pair(pe[:120]+'ACGTA'+pe[120:], length=120), 'other_or_unassessable'
    # End mates of the altered physical product also fit an incorrect reference
    # when only a tiny repeat overlap is assumed.
    repeat_pe = pe[:118]+'AAAAAAA'+pe[125:]
    repeat_wt = repeat_pe[:40]+('A' if repeat_pe[40]!='A' else 'C')+repeat_pe[41:]
    repeated = target.model_copy(update={'wt_sequence':repeat_wt, 'prime_edited_sequence':repeat_pe})
    yield 'three_nt_repeat_insertion', repeated, pair(repeat_pe[:121]+'A'+repeat_pe[121:], length=122), 'other_or_unassessable'
    yield 'short_repeat_wt_deletion', repeated, pair(repeat_wt[:121]+repeat_wt[122:], length=121), 'other_or_unassessable'
    yield 'unique_wt', target, pair(wt), 'exact_WT'
    yield 'unique_pe', target, pair(pe), 'exact_PE'
    yield 'exactly_ten_nt', target, pair(pe, length=125), 'exact_PE'
    left, _ = pair(pe, length=125)
    _, right = pair(pe, length=124)
    yield 'nine_nt', target, (left, right), 'other_or_unassessable'
    left, _ = pair(pe)
    _, right = pair(pe[:122]+'A'+pe[123:])
    yield 'mate_disagreement', target, (left, right), 'other_or_unassessable'
    yield 'extra_substitution', target, pair(pe[:55]+('A' if pe[55]!='A' else 'C')+pe[56:]), 'other_or_unassessable'
    repeat = Target(target_name='repeat',copy_name='copy1',wt_sequence='A'*200,
        prime_edited_sequence='A'*201,pegRNA_spacer='A'*20,pegRNA_extension='T'*30)
    yield 'multiple_repeat_placements', repeat, pair('A'*201), 'other_or_unassessable'


@pytest.mark.parametrize('name,target,records,expected', list(overlap_cases()), ids=lambda v:v if isinstance(v,str) else None)
def test_unique_full_product_overlap(name, target, records, expected):
    assert MIN_EXACT_PAIR_OVERLAP == 10
    assert exact_pair_class(records, [target]) == expected
    assert exact_pair_class(records, [target, target.model_copy(update={'copy_name':'shared'})]) == expected
    if name in ('zero_overlap_insertion', 'three_nt_repeat_insertion', 'short_repeat_wt_deletion'):
        ref = target.wt_sequence if name=='short_repeat_wt_deletion' else target.prime_edited_sequence
        left, right = records[0].sequence.decode(), reverse_complement(records[1].sequence.decode())
        # Demonstrate that the audited old predicate would have admitted this pair.
        assert max(len(left),len(right)) <= len(ref) <= len(left)+len(right)
        assert ref.startswith(left) and ref.endswith(right)


@pytest.mark.parametrize('runtime,code',[(RUNTIME_DIGEST,None),(None,'MISSING_REQUIRED_PROVENANCE'),('wrong','UNQUALIFIED_BACKEND_RUNTIME')])
def test_runtime_only_scopes_backend_metrics(archive, runtime, code):
    result = collect(archive, runtime_digest=runtime)
    precise = result.target_metrics.total_precise_pe
    assert precise.status=='REPORTABLE' and (precise.numerator,precise.denominator)==(20,55)
    backend = [result.target_metrics.target_crispresso_native_pe,
               *(r for copy in result.copies.values() for r in (copy.native,copy.precise))]
    for record in backend:
        assert record.status == ('BLOCKED' if code else 'REPORTABLE')
        if code:
            assert record.reason_codes == [code]
            assert record.numerator is record.denominator is None
    if code:
        assert not result.anchor_evidence['failures']
        assert result.anchor_evidence['comparison']['skipped_reason_codes'] == [code]


@pytest.mark.parametrize('field',COMPARISON_FIELDS)
def test_every_authoritative_anchor_integer_is_required(field):
    metrics=metrics_with_window([111,112])
    metrics['copy2']['native'][field]+=1
    result=evaluate_anchors(panel(),metrics)
    assert 'ANCHOR_DEPENDENT_NATIVE_RESULT' in result['reasons'] and not result['anchor_invariant']


@pytest.mark.parametrize('first,second',[
    ('nonzero','success'),('success','nonzero'),('nonzero','malformed'),
    ('malformed','success'),('counter','success'),('ambiguity','success'),
    ('launch','success'),('reference','success')])
def test_independent_anchor_failures_preserve_actual_reasons(archive,tmp_path,monkeypatch,first,second):
    attempted=[]
    by_copy=dict(copy1=first,copy2=second)
    codes={'nonzero':'BACKEND_EXECUTION_FAILED','malformed':'BACKEND_OUTPUT_MALFORMED',
           'counter':'BACKEND_COUNTER_RECONCILIATION_FAILED','ambiguity':'BACKEND_AMBIGUOUS_RECONCILIATION_FAILED',
           'launch':'BACKEND_EXECUTION_FAILED','reference':'BACKEND_REFERENCE_MISMATCH'}
    real_run = subprocess.run
    def execute(argv, **kwargs):
        if argv[0] != '/test/core': return real_run(argv, **kwargs)
        cwd = kwargs['cwd']
        copy=next(t.copy_name for t in panel() if t.wt_sequence==argv[argv.index('--amplicon_seq')+1])
        attempted.append(copy)
        kind=by_copy[copy]
        if kind=='launch': raise FileNotFoundError('Core executable unavailable')
        if kind=='nonzero': return subprocess.CompletedProcess(argv,13)
        shutil.copytree(archive/f'comparator/{copy}/output',Path(cwd)/'output')
        path=Path(cwd)/'output/CRISPResso_on_unrouted/CRISPResso2_info.json'
        if kind=='malformed': path.write_text('{')
        elif kind in ('counter','ambiguity','reference'):
            data=json.loads(path.read_text())
            if kind=='counter': data['running_info']['alignment_stats']['N_TOT_READS']+=1
            elif kind=='reference': data['results']['refs']['Reference']['sequence']='ACGT'
            else: data['results']['alignment_stats']['class_counts']['AMBIGUOUS']=1
            write_json(path,data)
        return subprocess.CompletedProcess(argv,0)
    monkeypatch.setattr(subprocess,'run',execute)
    result=run_metrics(analysis_root=archive/'analysis',sample_id='1B',targets=panel(),analysis_id='anchor-failure',
        output=tmp_path/'result',core=Executable('/test/core','2.3.4',{}))
    assert attempted==['copy1','copy2']
    failures={c:codes[k] for c,k in by_copy.items() if k!='success'}
    assert result.anchor_evidence['failures']==failures
    native=result.target_metrics.target_crispresso_native_pe
    assert native.status=='BLOCKED' and native.numerator is native.denominator is None
    assert set(failures.values()) <= set(native.reason_codes)
    assert 'MISSING_ANCHOR_RESULT' not in native.reason_codes
    assert result.target_metrics.total_precise_pe.status=='REPORTABLE'
    for copy,kind in by_copy.items():
        evidence=json.loads((tmp_path/f'result/comparator/{copy}/execution.json').read_text())
        assert evidence['status']==('completed' if kind=='success' else 'failed')
        assert evidence['return_code']==(None if kind=='launch' else 13 if kind=='nonzero' else 0)


def test_known_prelaunch_version_failure_is_not_reported_as_missing(archive,tmp_path,monkeypatch):
    real_run=subprocess.run
    def execute(argv, **kwargs):
        if argv[0]=='/test/core': raise AssertionError('unqualified backend must not launch')
        return real_run(argv, **kwargs)
    monkeypatch.setattr(subprocess,'run',execute)
    result=run_metrics(analysis_root=archive/'analysis',sample_id='1B',targets=panel(),analysis_id='version-precondition',
        routing_root=archive/'routing',output=tmp_path/'result',core=Executable('/test/core','2.3.3',{}))
    backend=[result.target_metrics.target_crispresso_native_pe,
             *(r for c in result.copies.values() for r in (c.native,c.precise))]
    assert all(r.reason_codes==['UNQUALIFIED_BACKEND_RUNTIME'] for r in backend)
    assert result.target_metrics.total_precise_pe.denominator==55
    for kind in ('comparator','copies'):
        for copy in ('copy1','copy2'):
            evidence=json.loads((tmp_path/f'result/{kind}/{copy}/execution.json').read_text())
            assert evidence['status']=='not_started' and evidence['return_code'] is None


def test_runtime_precondition_prevents_backend_launch_without_missing_anchor_reason(archive,tmp_path,monkeypatch):
    real_run = subprocess.run
    def forbidden(argv, **kwargs):
        if argv[0] == '/test/core': raise AssertionError('backend must not launch')
        return real_run(argv, **kwargs)
    monkeypatch.setattr(subprocess,'run',forbidden)
    result=run_metrics(analysis_root=archive/'analysis',sample_id='1B',targets=panel(),analysis_id='precondition',
        routing_root=archive/'routing',output=tmp_path/'result',core=Executable('/test/core','2.3.4',{}),runtime_digest='wrong')
    assert result.target_metrics.target_crispresso_native_pe.reason_codes==['UNQUALIFIED_BACKEND_RUNTIME']
    assert result.target_metrics.total_precise_pe.denominator==55
    assert not (tmp_path/'result/comparator').exists()


@pytest.mark.parametrize('encoded',[[],{'_type':'np.ndarray','value':[]}])
def test_empty_window_does_not_block_prepared_exact(archive,tmp_path,encoded):
    root=tmp_path/'run';shutil.copytree(archive,root)
    mutate_info(root,lambda d:d['results']['refs']['Reference'].update(include_idxs=encoded))
    result=collect(root)
    assert result.target_metrics.target_crispresso_native_pe.reason_codes==['EMPTY_AUTHORITATIVE_QUANTIFICATION_WINDOW']
    assert result.target_metrics.total_precise_pe.denominator==55


@pytest.mark.parametrize('attack',['ordinary','ambiguous','discarded','float','partial'])
def test_aligned_partition_model_rejects_unreconciled_counts(archive,attack):
    data=collect(archive).model_dump()
    native=data['target_metrics']['target_crispresso_native_pe']
    if attack=='partial': native['ambiguous_aligned_reads']=None
    elif attack=='float': native['ambiguous_aligned_reads']=0.0
    else: native[attack+'_classified_aligned_reads' if attack=='ordinary' else attack+'_aligned_reads']+=1
    with pytest.raises(ValidationError): MetricResult.model_validate(data)


@pytest.mark.parametrize('attack',['ambiguous','discarded','unknown_row'])
def test_backend_aligned_partition_rejects_unexplained_differences(archive,tmp_path,attack):
    child=tmp_path/'child';shutil.copytree(archive/'comparator/copy1/output/CRISPResso_on_unrouted',child)
    path=child/'CRISPResso2_info.json';data=json.loads(path.read_text())
    if attack=='ambiguous': data['results']['alignment_stats']['class_counts']['AMBIGUOUS']=1
    elif attack=='discarded': data['results']['alignment_stats']['counts_discarded']['Reference']=1
    else:
        running=data['running_info'];path_zip=child/running['allele_frequency_table_zip_filename']
        with zipfile.ZipFile(path_zip) as z: contents=z.read(running['allele_frequency_table_filename']).decode()
        rows=list(csv.DictReader(io.StringIO(contents),delimiter='\t'))
        rows[0]['Reference_Name']='UNKNOWN_REFERENCE'
        text=io.StringIO();writer=csv.DictWriter(text,fieldnames=rows[0].keys(),delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(rows)
        with zipfile.ZipFile(path_zip,'w') as z:z.writestr(running['allele_frequency_table_filename'],text.getvalue())
    write_json(path,data)
    with pytest.raises(MetricContractError) as exc:
        parse_child(child,routed_pairs=125,one_input_record_per_pair=True)
    assert exc.value.code=='BACKEND_AMBIGUOUS_RECONCILIATION_FAILED'
