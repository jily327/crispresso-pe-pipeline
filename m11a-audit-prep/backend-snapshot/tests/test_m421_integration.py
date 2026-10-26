"""Actual pinned Core reproduction of copy-selective target populations."""
import json
import os
from pathlib import Path

import pytest

from peanalyzer.backend.comparator import run_comparator
from peanalyzer.metrics import collect_metrics,run_metrics,reaggregate
from peanalyzer.metrics.production import RUNTIME_DIGEST
from test_m42_integration import prepare,core
from test_m421 import copy_panel,records_for,canonical

pytestmark=[pytest.mark.crispresso_integration,
            pytest.mark.skipif(os.environ.get('M421_INTEGRATION')!='1',reason='set M421_INTEGRATION=1 with pinned Core 2.3.4')]


def root_path(tmp_path,name):
    return (Path(os.environ['M421_RESULTS_DIR']) if 'M421_RESULTS_DIR' in os.environ else tmp_path)/name


@pytest.mark.parametrize('left,right',[(150,150),(125,125),(124,125)])
def test_actual_copy_selective_geometry_never_reports_surviving_copy(tmp_path,left,right):
    root=root_path(tmp_path,f'cross_copy_{left}_{right}');targets=copy_panel()
    prepare(root,records_for(targets,left,right))
    engine=core();raw=run_comparator(root/'analysis','1B',targets,root/'raw',engine,runtime_identity={'image_digest':RUNTIME_DIGEST})
    expected=(20,40) if left==150 else (18,20)
    assert all((p['native']['numerator'],p['native']['denominator'])==expected for p in raw['backend_metrics'].values())
    policies=[dict(policy_id=str(n),max_extra_substitutions=n) for n in (0,1)]
    args=dict(analysis_root=root/'analysis',sample_id='1B',targets=targets,analysis_id=root.name,
        comparator_root=root/'raw',runtime_digest=RUNTIME_DIGEST)
    baseline=collect_metrics(**args);result=collect_metrics(**args,tolerance_policies=policies)
    assert canonical(result)==canonical(baseline)
    native=result.target_metrics.target_crispresso_native_pe;exact=result.target_metrics.total_precise_pe
    if left==150:assert native.status=='REPORTABLE' and (native.numerator,native.denominator)==(20,40)
    else:assert native.status=='BLOCKED' and 'COPY_DEPENDENT_BACKEND_MERGEABILITY' in native.reason_codes
    if left>=125:
        assert exact.status=='REPORTABLE' and (exact.numerator,exact.denominator)==(20,40)
        assert all(r.status=='REPORTABLE' and (r.numerator,r.denominator)==(20,40) for r in result.derived_metrics['target'].values())
    else:
        assert exact.status=='NOT_ASSESSABLE' and exact.numerator is exact.denominator is None
        assert 'COPY_DEPENDENT_PRODUCT_OBSERVABILITY' in exact.reason_codes
        assert exact.products.exclusion_reason_counts=={'COPY_DEPENDENT_PRODUCT_OBSERVABILITY':40}
        assert all(r.status=='NOT_ASSESSABLE' and r.excluded==40 for r in result.derived_metrics['target'].values())
    (root/'result.json').write_text(result.model_dump_json(indent=2)+'\n')
    (root/'targets.json').write_text(json.dumps([t.model_dump() for t in targets],indent=2)+'\n')
    (root/'raw_backend.json').write_text(json.dumps(raw,indent=2)+'\n')
    for key,evidence in result.product_evidence.items():assert reaggregate(evidence,policies)==result.derived_metrics[key]
    # Invalid policies survive production publication, and selective geometries
    # never launch a target comparator. The long control executes real Core.
    mixed=policies+[dict(policy_id='duplicate'),dict(policy_id='duplicate'),None,{}]
    launched=run_metrics(analysis_root=root/'analysis',sample_id='1B',targets=targets,analysis_id=root.name,
        output=root/'production',core=engine,tolerance_policies=mixed)
    assert (root/'production/result.json').is_file()
    assert launched.target_metrics==result.target_metrics
    assert len(launched.derived_metrics['target'])==6
    assert all(r.status=='BLOCKED' for k,r in launched.derived_metrics['target'].items() if k not in ('0','1'))
    if left!=150:assert not (root/'production/comparator').exists()


def test_actual_copy_specific_repeat_excludes_target_length_class(tmp_path):
    root=root_path(tmp_path,'copy_specific_repeat');targets=copy_panel('repeat')
    prepare(root,records_for(targets,150,106))
    result=run_metrics(analysis_root=root/'analysis',sample_id='1B',targets=targets,analysis_id=root.name,
        output=root/'production',core=core(),tolerance_policies=[dict(policy_id=str(n),max_extra_substitutions=n) for n in (0,1)])
    exact=result.target_metrics.total_precise_pe
    assert exact.status=='NOT_ASSESSABLE' and 'COPY_DEPENDENT_PRODUCT_OBSERVABILITY' in exact.reason_codes
    assert exact.products.exclusion_reason_counts=={'COPY_DEPENDENT_PRODUCT_OBSERVABILITY':40}
    assert all(r.status!='REPORTABLE' for r in result.derived_metrics['target'].values())
    (root/'targets.json').write_text(json.dumps([t.model_dump() for t in targets],indent=2)+'\n')
