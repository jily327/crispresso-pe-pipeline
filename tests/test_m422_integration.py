"""Pinned actual Core controls and target/copy scope independence."""
import json
import os
from pathlib import Path

import pytest

from peanalyzer.backend.comparator import run_comparator
from peanalyzer.metrics import collect_metrics, run_metrics, reaggregate
from peanalyzer.metrics.production import RUNTIME_DIGEST
from peanalyzer.remediation import indel_designs, pair
from peanalyzer.routing import route_analysis
from test_m421 import canonical
from test_m422 import fixture, check_result, POLICIES, trim_r1, STATE_REASON
from test_m42_integration import prepare, core

pytestmark = [pytest.mark.crispresso_integration,
    pytest.mark.skipif(os.environ.get('M422_INTEGRATION') != '1', reason='set M422_INTEGRATION=1 with pinned Core 2.3.4')]


def root_path(tmp_path, name):
    return Path(os.environ.get('M422_RESULTS_DIR', tmp_path))/name


@pytest.mark.parametrize('name', ['fixed', 'copy2_1_all'])
def test_actual_backend_cannot_rescue_selected_target_subset(tmp_path, name):
    root = root_path(tmp_path, name)
    targets, records, expected, reason = fixture(name)
    prepare(root, records)
    raw = run_comparator(root/'analysis', '1B', targets, root/'raw', core(),
                         runtime_identity={'image_digest': RUNTIME_DIGEST})
    assert all((v['native']['numerator'], v['native']['denominator']) == (18, 20)
               for v in raw['backend_metrics'].values())
    args = dict(analysis_root=root/'analysis', sample_id='1B', targets=targets,
        analysis_id=name, comparator_root=root/'raw', runtime_digest=RUNTIME_DIGEST)
    result = collect_metrics(**args, tolerance_policies=POLICIES)
    assert canonical(result) == canonical(collect_metrics(**args))
    check_result(result, expected, reason)
    native = result.target_metrics.target_crispresso_native_pe
    assert native.status == 'BLOCKED' and 'COPY_DEPENDENT_BACKEND_MERGEABILITY' in native.reason_codes
    policies = POLICIES + [None, {}, dict(policy_id='dup'), dict(policy_id='dup')]
    launched = run_metrics(analysis_root=root/'analysis', sample_id='1B', targets=targets,
        analysis_id=name, output=root/'production', core=core(), tolerance_policies=policies)
    assert launched.target_metrics == result.target_metrics
    assert (root/'production/result.json').is_file() and not (root/'production/comparator').exists()
    assert all(r.status == 'BLOCKED' for k,r in launched.derived_metrics['target'].items() if k not in ('0','1'))
    assert reaggregate(result.product_evidence['target'], POLICIES) == result.derived_metrics['target']
    (root/'result.json').write_text(result.model_dump_json(indent=2)+'\n')
    (root/'targets.json').write_text(json.dumps([t.model_dump() for t in targets],indent=2)+'\n')
    (root/'raw_backend.json').write_text(json.dumps(raw,indent=2)+'\n')


def test_actual_qualified_copy_survives_target_selective_failure(tmp_path):
    root = root_path(tmp_path, 'copy_independence')
    targets = next(ts for d,ts in indel_designs() if d['id'] == 'deletion_1_seed29')
    records = []
    for t in targets:
        for state,seq in [('WT',t.wt_sequence),('PE',t.prime_edited_sequence)]:
            for i in range(10):
                p = pair(seq,identifier=f'{t.copy_name}_{state}_{i}',length=150 if t.copy_name=='copy1' else 125)
                records.append(trim_r1(p,1) if t.copy_name=='copy2' and state=='PE' else p)
    prepare(root,records)
    route_analysis(root/'analysis','1B',targets,root/'routing')
    result = run_metrics(analysis_root=root/'analysis',sample_id='1B',targets=targets,
        analysis_id=root.name,routing_root=root/'routing',output=root/'production',
        core=core(),tolerance_policies=POLICIES)
    check_result(result,None,STATE_REASON)
    copy = result.copies['copy1']
    assert copy.native.status == copy.precise.status == 'REPORTABLE'
    assert (copy.native.numerator,copy.native.denominator) == (10,20)
    assert (copy.precise.numerator,copy.precise.denominator) == (10,20)
    assert all(r.status == 'REPORTABLE' and (r.numerator,r.denominator)==(10,20)
               for r in result.derived_metrics['copy1'].values())
    (root/'targets.json').write_text(json.dumps([t.model_dump() for t in targets],indent=2)+'\n')
