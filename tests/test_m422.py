"""Whole-target observability: prevent selecting a biological subpopulation."""
import json
import subprocess
import sys

import pytest

from peanalyzer.fastq import FastqRecord
from peanalyzer.metrics import collect_metrics, reaggregate
from peanalyzer.metrics.family import prepared_evidence
from peanalyzer.metrics.production import RUNTIME_DIGEST, metric
from peanalyzer.metrics.products import prepared_products
from peanalyzer.remediation import indel_designs, pair, panel
from test_m42 import mutate
from test_m421 import copy_panel, records_for
from test_m42_integration import prepare

POLICIES = [dict(policy_id=str(n), max_extra_substitutions=n) for n in (0, 1)]
COPY_REASON = 'COPY_DEPENDENT_PRODUCT_OBSERVABILITY'
STATE_REASON = 'STATE_DEPENDENT_PRODUCT_LENGTH_ASSESSABILITY'


def trim_r1(records, bases):
    left, right = records
    return (FastqRecord(left.header, left.sequence[:-bases] + b'\n', left.plus,
                        left.quality_line.rstrip(b'\r\n')[:-bases] + b'\n'), right)


def fixture(name):
    """Deterministic biological truths; no fraction heuristic in production."""
    targets = copy_panel()
    records = records_for(targets, 125, 125)
    expected, reason = (20, 40), None
    if name.startswith('copy'):
        copy, amount, portion = name.split('_')
        records = [trim_r1(p, int(amount)) if copy.encode() in p[0].header and
                   (portion == 'all' or int(p[0].header.split(b'_')[-1].split(b'/')[0]) % 2 == 0) else p
                   for p in records]
        expected, reason = None, COPY_REASON
    elif name.startswith(('deletion_', 'insertion_')):
        kind, state, portion = name.split('_')
        design = 'deletion_1_seed29' if kind == 'deletion' else 'insertion_12_seed11'
        targets = next(ts for d, ts in indel_designs() if d['id'] == design)[:1]
        t = targets[0]; records = []
        for label, seq in [('WT', t.wt_sequence), ('PE', t.prime_edited_sequence)]:
            for i in range(10):
                selected = label == state and (portion == 'all' or i % 2 == 0)
                length = (128 if selected else 150) if kind == 'insertion' else 125
                p = pair(seq, identifier=f'{label}_{i}', length=length)
                records.append(trim_r1(p, 1) if kind == 'deletion' and selected else p)
        expected, reason = None, STATE_REASON
    elif name == 'safe_mixed':
        records = records_for(targets[:1], 150, 150) + records_for(targets, 125, 125)[20:]
    elif name == 'symmetric_unobservable':
        records = records_for(targets, 100, 100); expected = None
    elif name == 'ordinary_snp':
        targets = panel()[:1]; t = targets[0]; records = []
        for state, seq in [('WT', t.wt_sequence), ('PE', t.prime_edited_sequence)]:
            for i in range(10): records.append(pair(seq, identifier=f'{state}_{i}'))
            records.append(pair(mutate(seq, 45), identifier=f'{state}_extra'))
        expected = (10, 20)
    elif name != 'fixed':
        raise ValueError(name)
    return targets, records, expected, reason


CASES = ['fixed', 'safe_mixed', 'symmetric_unobservable', 'ordinary_snp'] + [
    f'{copy}_{amount}_all' for copy in ('copy1', 'copy2') for amount in range(1, 7)] + [
    f'{copy}_3_half' for copy in ('copy1', 'copy2')] + [
    f'{kind}_{state}_{portion}' for kind in ('deletion', 'insertion')
    for state in ('WT', 'PE') for portion in ('all', 'half')]


def evaluate(root, name):
    targets, records, expected, reason = fixture(name)
    prepare(root, records)
    result = collect_metrics(analysis_root=root/'analysis', sample_id='1B', targets=targets,
        analysis_id=name, comparator_root=root/'absent', runtime_digest=RUNTIME_DIGEST,
        tolerance_policies=POLICIES)
    return result, expected, reason


def check_result(result, expected, reason):
    exact = result.target_metrics.total_precise_pe
    families = result.derived_metrics['target']
    for row in [exact, *families.values()]:
        if expected is None:
            assert row.status == 'NOT_ASSESSABLE'
            assert row.numerator is row.denominator is None
            assert row.model_dump().get('fraction') is None
            if reason: assert reason in row.reason_codes
        else:
            assert row.status == 'REPORTABLE'
    if expected is not None:
        assert (exact.numerator, exact.denominator) == expected
        assert (families['0'].numerator, families['0'].denominator) == expected
    if reason:
        assert exact.products.exclusion_reason_counts[reason] > 0
        assert all(r.wt_family == r.pe_family == 0 and r.excluded == r.classification_input_reads
                   for r in families.values())
    return exact


@pytest.mark.parametrize('name', CASES)
def test_target_population_is_not_selected_by_geometry(tmp_path, name):
    result, expected, reason = evaluate(tmp_path/'case', name)
    check_result(result, expected, reason)
    evidence = json.loads(result.product_evidence['target'].model_dump_json())
    assert reaggregate(evidence, POLICIES) == result.derived_metrics['target']
    if name == 'ordinary_snp':
        assert (result.derived_metrics['target']['1'].numerator,
                result.derived_metrics['target']['1'].denominator) == (11, 22)


@pytest.mark.parametrize('reason', [COPY_REASON, STATE_REASON, 'STATE_DEPENDENT_PRODUCT_OBSERVABILITY'])
def test_stored_evidence_selective_failure_precedes_family_aggregation(tmp_path, reason):
    result, _, _ = evaluate(tmp_path/'case', 'copy2_1_all')
    products = result.target_metrics.total_precise_pe.products.model_copy(deep=True)
    products.exclusion_reason_counts = {reason: 20}
    exact = metric('total_precise_pe','precise','target_all_prepared','target',40,products=products)
    assert exact.status == 'NOT_ASSESSABLE' and exact.numerator is exact.denominator is None
    assert exact.reason_codes == [reason]
    evidence = result.product_evidence['target'].model_dump()
    for row in evidence['products']:
        if not row['assessable']: row['reason_codes'] = [reason]
    policies = POLICIES + [None, {}, dict(policy_id='duplicate'), dict(policy_id='duplicate')]
    outputs = reaggregate(evidence, policies)
    assert all(outputs[k].status == 'NOT_ASSESSABLE' and outputs[k].reason_codes == [reason] for k in ('0', '1'))
    assert all(r.status == 'BLOCKED' for k, r in outputs.items() if k not in ('0', '1'))
    script = "import json,sys; from peanalyzer.metrics import reaggregate; v=json.load(sys.stdin); print(json.dumps({k:r.model_dump() for k,r in reaggregate(v['evidence'],v['policies']).items()}))"
    observed = json.loads(subprocess.check_output([sys.executable, '-c', script], cwd=tmp_path,
        input=json.dumps(dict(evidence=evidence, policies=policies)), text=True))
    assert observed == {k:r.model_dump() for k,r in outputs.items()}


@pytest.mark.parametrize('origin', ['copy1_WT', 'copy1_PE', 'copy2_WT', 'copy2_PE'])
def test_one_selectively_excluded_pair_is_sufficient(tmp_path, origin):
    targets, records, _, _ = fixture('fixed')
    chosen = next(i for i,p in enumerate(records) if origin.encode() in p[0].header)
    records[chosen] = trim_r1(records[chosen], 1)
    root = tmp_path/'single'; prepare(root, records)
    result = collect_metrics(analysis_root=root/'analysis',sample_id='1B',targets=targets,
        analysis_id=origin,comparator_root=root/'absent',runtime_digest=RUNTIME_DIGEST,tolerance_policies=POLICIES)
    exact = check_result(result,None,COPY_REASON)
    assert exact.products.exclusion_reason_counts == {COPY_REASON:1}
    assert exact.products.exact_wt + exact.products.exact_pe == 39


def test_nonselective_unassessable_pair_does_not_block_surviving_exact_products(tmp_path):
    targets = panel()[:1]
    records = [pair(targets[0].wt_sequence, identifier='wt'),
               pair(targets[0].prime_edited_sequence, identifier='pe'),
               pair(targets[0].wt_sequence, identifier='short', length=50)]
    paths = [tmp_path/f'R{m}.fastq' for m in (1, 2)]
    for m,path in enumerate(paths): path.write_bytes(b''.join(p[m].to_bytes() for p in records))
    products = prepared_products(paths, targets)
    result = metric('total_precise_pe','precise','target_all_prepared','target',3,products=products)
    assert result.status == 'REPORTABLE' and (result.numerator,result.denominator) == (1,2)
    evidence = prepared_evidence(paths,targets,population_id='target',population_scope='target_all_prepared',
        copy_id=None,source_input_reads=3)
    assert all(r.status == 'REPORTABLE' and (r.numerator,r.denominator) == (1,2)
               for r in reaggregate(evidence,POLICIES).values())
