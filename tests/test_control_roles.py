"""SCI-04 independent count oracles and role-aware biological design."""
import csv

import pytest

from test_site_statistics import inputs
from m5_fixtures import dataset, read_samples, result_document, write_json, write_samples
from peanalyzer.reporting import build_report_spec
from peanalyzer.statistics import stats


def fixture(root, paired=False):
    options = dataset(root, replicates=2, targets=('T1',), paired=paired)
    for name, n, d in [('A001',1,10),('A002',90,100)]:
        write_json(root/f'{name}-T1.json', result_document('barcode-'+name, 'T1', n,d))
    return options


def set_role(options, role, *, share_identity=False):
    rows = read_samples(options['samples_path'])
    for r in rows:
        r['sample_role'] = role if r['sample_name'] == 'A002' else 'experimental'
        if share_identity and r['sample_name'] == 'A002':
            r['biological_replicate'] = rows[0]['biological_replicate']
            r['block_id'] = rows[0]['block_id']
    write_samples(options['samples_path'],rows)


@pytest.mark.parametrize('role',['negative_control','pcr_negative_control','no_template_control','technical_replicate'])
@pytest.mark.parametrize('paired',[False,True])
def test_positive_depth_qc_cannot_satisfy_biological_minimum(tmp_path,role,paired):
    options=fixture(tmp_path,paired)
    set_role(options,role,share_identity=(role=='technical_replicate'))
    result=stats(**options,output=tmp_path/'result')
    target='total_precise_pe'
    group=next(g for g in result.group_summaries if g.metric_name==target and g.condition.treatment=='A')
    assert group.reportable_count==group.expected_sample_count==1
    assert group.reportable_sample_ids==['A001'] and group.sample_sd_biological_sample_fraction is None
    assert group.mean_biological_sample_fraction==group.pooled_read_fraction==0.1
    contrast=next(c for c in result.contrasts if c.metric_name==target)
    assert contrast.status=='NOT_ASSESSABLE' and contrast.p_value is contrast.q_value is None
    assert contrast.reason_codes==['INSUFFICIENT_BIOLOGICAL_REPLICATES']
    assert contrast.used_group_a_sample_ids==['A001']
    assert len(contrast.complete_blocks)==int(paired)
    assert all('A002' not in c.expected_sample_ids for c in result.group_summaries)
    assert {o.metric_name for o in result.observations if o.sample_name=='A002'} == {o.metric_name for o in result.observations if o.sample_name=='A001'}
    with (tmp_path/'result/control_and_technical_qc.tsv').open() as f:
        qc=next(r for r in csv.DictReader(f,delimiter='\t') if r['metric_name']==target)
    assert (qc['sample_name'],qc['sample_role'],qc['numerator'],qc['denominator'],qc['fraction'])==('A002',role,'90','100','0.9')
    spec=build_report_spec(result)
    assert spec['inventory']['biological_samples']==3
    assert all(p['sample_name']!='A002' for s in spec['series'] for p in s['points'])
    assert all(row['sample_role']==role and row['biological_eligible'] is False for row in spec['control_qc'])


def test_biological_control_uses_full_counts_and_technical_rows_are_separate(tmp_path):
    opts=fixture(tmp_path)
    set_role(opts,'biological_negative_control')
    result=stats(**opts)
    group=next(g for g in result.group_summaries if g.metric_name=='total_precise_pe' and g.condition.treatment=='A')
    assert group.reportable_count==2 and group.mean_biological_sample_fraction==.5 and group.pooled_read_fraction==91/110
    assert result.contrasts[0].status=='REPORTABLE'
    assert all(o['biological_eligible'] for o in build_report_spec(result)['control_qc'])


def test_site_roles_and_dedicated_workbook_qc(inputs,tmp_path):
    from peanalyzer.gui.scientific_workbook import scientific_sheets
    from peanalyzer.gui.models import Source
    from types import SimpleNamespace
    opts,_=inputs
    set_role(opts,'no_template_control')
    result=stats(**opts)
    for g in result.group_summaries:
        assert 'A002' not in g.expected_sample_ids
    call=next(o for o in result.observations if o.sample_name=='A002' and o.metric_name=='intended_sites.two_site_q30.double_edit' and o.copy_name is None)
    assert (call.numerator,call.denominator,call.fraction)==(80,100,.8)
    item=SimpleNamespace(**(call.model_dump() | dict(target=call.target_name,biological_eligible=False,
        reasons=call.reason_codes,source=Source(name='intended_sites.json',sha256='a'*64,artifact_id='a',kind='json',downloadable=True,size_bytes='1'))))
    item.numerator,item.denominator=str(item.numerator),str(item.denominator)
    sheets=scientific_sheets(SimpleNamespace(mode='precise_edit',observations=[item]))
    rows,pct=sheets['Control and technical QC']
    assert rows[1][1:4]==('barcode-A002','no_template_control',False) and rows[1][9:12]==('80','100',.8) and pct=={12}


@pytest.mark.parametrize('role',['pcr_negative_control','no_template_control'])
def test_empty_control_role_and_workbook_qc(tmp_path,role):
    import json
    from openpyxl import load_workbook
    from m8_fixtures import fixture as nuclease
    from m7_fixtures import write_csv
    from peanalyzer.gui.summary_workbook import FILENAME
    from peanalyzer.gui.workspace import WorkspaceStore
    from peanalyzer.workflow import execute_workflow, verify_workflow_output
    from test_empty_controls import version_probe

    options = nuclease(tmp_path/'inputs', populations=[[],[]])
    rows = read_samples(options['samples'])
    for row in rows:
        row['sample_role'] = role
    write_csv(options['samples'], list(rows[0]), rows)
    options['crispresso'] = version_probe(tmp_path/'CRISPResso')
    execute_workflow(**options)
    root = options['output']
    verify_workflow_output(root)
    store = WorkspaceStore([])
    view = store.register_completed('Control QC',root,finalize=True)
    qc = [o for o in view.observations if o.metric_name=='indel_fraction']
    assert len(qc)==2 and all(o.sample_role==role and o.biological_eligible is False and o.fraction is None for o in qc)
    with (root/'statistics/control_and_technical_qc.tsv').open() as stream:
        assert all(r['sample_role']==role and r['fraction']=='' for r in csv.DictReader(stream,delimiter='\t'))
    assert all(g['expected_sample_count']==g['reportable_count']==0 for g in json.loads((root/'statistics/result.json').read_bytes())['group_summaries'])
    book = load_workbook(root/FILENAME,read_only=True)
    try:
        rows=list(book['Control and technical QC'].values)[1:]
        assert rows and all(r[2]==role and r[3] is False and r[11] is None for r in rows)
    finally:
        book.close()


def test_historical_read_only_and_explicit_reanalysis(tmp_path):
    from peanalyzer.statistical_models import StatisticsResult
    from peanalyzer.statistics import calculate_contrasts, load_contrasts

    opts=fixture(tmp_path)
    original=stats(**opts)
    raw=original.model_dump()
    del raw['provenance']['invocation_parameters']['biological_role_policy']
    for o in raw['observations']:
        if o['sample_name']=='A002':o['sample_role']='negative_control'
    archived=StatisticsResult.model_validate(raw)
    frozen=archived.model_dump_json()
    assert archived.contrasts[0].status=='REPORTABLE'
    recalculated=calculate_contrasts(archived,load_contrasts(opts['contrasts_path'])[0])
    assert archived.model_dump_json()==frozen
    assert recalculated.contrasts[0].status=='NOT_ASSESSABLE'
