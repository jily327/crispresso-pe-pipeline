"""Full-sample native multi-reference Core and independently tagged molecule truth."""
import csv
import gzip
import json
import os
from pathlib import Path

import pytest
from m7_fixtures import write_csv
from m8_fixtures import CASES, WT, fixture, insert, substitute, target
from test_multicopy_nuclease import B, MIXED, panel
from peanalyzer.workflow import execute_workflow, verify_workflow_output


def replace(seq,p):
    return seq[:p]+'N'+seq[p+1:]


def make_case(case, root, monkeypatch):
    if case == 'SCI03':
        opts=fixture(root/'inputs',[[('WT',1)]])
        source=Path(__file__).parents[1]/'docs/validation/remediation/nuclease/audit-inputs'
        for role in ('samples','targets','config','r1','r2'):
            opts[role]=source/opts[role].name
        return opts,{'combined':(2,9),'a':(2,6),'b':(0,3)}
    scope,window=case.split('-')
    if scope == 'single':
        populations={'zero_event':(WT,8), 'cut_insertion':(insert(WT,105),1)}
        targets=[target(tigr_window=window)]
        truth={'combined':(1,9)}
    else:
        # Positions below are in the chr03g layout. chr13g has a 3-bp prefix.
        # Each tuple specifies molecule count, expected assessable windows,
        # and windows in which at least one included indel is known by design.
        all_windows={'W1','W2','W3','W4'}
        products={
            'wt_a':(WT,4,'chr03g',all_windows,set()), 'wt_b':(B,3,'chr13g',all_windows,set()),
            'left_cut_insertion':(insert(WT,105),1,'chr03g',all_windows,all_windows),
            'deletion_across_boundary':(WT[:103]+WT[107:],1,'chr03g',all_windows,all_windows),
            'insertion_deletion':(insert(B,115)[:108]+insert(B,115)[109:],1,'chr13g',all_windows,all_windows),
            'substitution':(substitute(B,111),1,'chr13g',all_windows,set()),
            'unknown_between_W1_intervals':(insert(replace(WT,108),105),2,'chr03g',{'W1'},{'W1'}),
            'expanded_window_only':(B[:98]+B[99:],1,'chr13g',all_windows,{'W4'}),
            'conflicting_copy_markers':(MIXED,1,None,all_windows,set()),
            'ambiguous_origin_insertion':(insert(MIXED,105),1,None,all_windows,all_windows),
        }
        populations={k:(seq,n) for k,(seq,n,_,_,_) in products.items()}
        truth={}
        for group in ('combined','chr03g','chr13g'):
            rows=[(n,window in events) for _,n,c,eligible,events in products.values()
                  if window in eligible and (group=='combined' or group==c)]
            truth[group]=(sum(n for n,event in rows if event),sum(n for n,_ in rows))
        targets=panel(window)
    for name,(seq,n) in populations.items():
        monkeypatch.setitem(CASES,name,(seq,None))
    opts=fixture(root/'inputs',[[(name,n) for name,(_,n) in populations.items()]])
    write_csv(opts['targets'],list(targets[0].model_dump()),[t.model_dump() for t in targets])
    return opts,truth


@pytest.mark.crispresso_integration
@pytest.mark.skipif(os.environ.get('M8_INTEGRATION') != '1',reason='requires pinned Core with reports and plots')
@pytest.mark.parametrize('case',['SCI03',*[s+'-'+w for s in ('single','multi') for w in ('W1','W2','W3','W4')]])
def test_nuclease_window_and_native_references(case,tmp_path,monkeypatch):
    root=Path(os.environ.get('NUCLEASE_REMEDIATION_OUTPUT',tmp_path))/case
    root.mkdir(parents=True)
    opts,truth=make_case(case,root,monkeypatch)
    opts['crispresso']=os.environ.get('M3_CORE_EXECUTABLE','CRISPResso')
    execute_workflow(**opts)
    verify_workflow_output(opts['output'])
    cell=opts['output']/'metrics/bc001/T1'
    m=json.loads((cell/'result.json').read_text())
    groups={'combined':m['combined'],**m['copies']} if 'copies' in m else {'combined':m}
    counts={name:(g['metrics']['indel_fraction']['numerator'],g['metrics']['indel_fraction']['denominator']) for name,g in groups.items()}
    assert counts == truth
    if 'copies' in m:
        assert m['window_observability'] == 'selected_interval_union_v2'
        expected_exclusions={} if case in ('SCI03','multi-W1') else {'UNKNOWN_BASE_IN_SELECTED_INTERVAL':2}
        assert m['aligned_exclusion_reasons'] == expected_exclusions
    native=json.loads((cell/'native_runs.json').read_text())
    runs=native['runs']
    assert len(runs) == (3 if 'copies' in m else 1)
    for r in runs:
        assert r['execution_status']=='COMPLETED' and r['extraction_status']=='PASS',r
        assert r['counts']['backend_input_reads']==native['input_pairs']
        assert r['population']=='all_prepared_pairs'
        assert 'report' in r['paths'] and (cell/r['paths']['report']).is_file()
    if 'copies' in m:
        original,=(r for r in runs if r['id']=='native_panel')
        assert list(original['per_reference']) == [t['copy_name'] for t in m['targets']]
    plan=json.loads((opts['output']/'workflow/plan.json').read_text())
    (root/'oracle.json').write_text(json.dumps(dict(case=case,expected=truth,observed=counts,
        identity=plan['software_identity'],aligned_exclusion_reasons=m.get('aligned_exclusion_reasons'),
        native_input_pairs=native['input_pairs'],sources={r['id']:dict(paths=r['paths'],counts=r['counts'],
        per_reference=r['per_reference'],sha256=r['sha256'],recount_status=r['recount_status'],
        runtime_identity_status=r['runtime_identity_status']) for r in runs}),indent=2,sort_keys=True)+'\n')


def test_stage_inventory_orders_native_report_sibling_before_directory(tmp_path):
    from peanalyzer.workflow_storage import inventory
    stage=tmp_path/'metrics'
    (stage/'CRISPResso_on_x').mkdir(parents=True)
    (stage/'CRISPResso_on_x'/'CRISPResso2_info.json').write_text('{}')
    (stage/'CRISPResso_on_x.html').write_text('report')
    assert [a.path for a in inventory(tmp_path,'metrics')] == [
        'metrics/CRISPResso_on_x.html','metrics/CRISPResso_on_x/CRISPResso2_info.json']


def test_sci03_original_native_rows_preserve_history_and_reconcile_selected_intervals():
    from peanalyzer.nuclease.models import MulticopyNucleaseResult
    from peanalyzer.nuclease.multicopy import calculate

    frozen=Path(__file__).parents[1]/'docs/validation/remediation/nuclease/audit-inputs/audited-result.json.gz'
    original=MulticopyNucleaseResult.model_validate_json(gzip.decompress(frozen.read_bytes()))
    assert original.window_observability is None
    assert (original.combined.metrics['indel_fraction'].numerator,original.combined.aligned_reads)==(0,7)
    reasons={}
    pop,combined,copies=calculate(original.targets,original.reference_runs,original.merged_counts,exclusion_counts=reasons)
    actual={k:(g.metrics['indel_fraction'].numerator,g.aligned_reads) for k,g in [('combined',combined),*copies.items()]}
    assert actual=={'combined':(2,9),'a':(2,6),'b':(0,3)} and pop['aligned_unassessable_reads']==0 and reasons=={}
