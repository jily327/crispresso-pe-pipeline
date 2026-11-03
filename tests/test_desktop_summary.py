"""Presentation export agrees with authoritative observations; counts stay exact."""
import json
from types import SimpleNamespace
import pytest
from openpyxl import load_workbook
from peanalyzer.gui.summary_workbook import write_summary, FILENAME, HEADERS
from peanalyzer.gui.workspace import WorkspaceStore, snapshot
from peanalyzer.workflow_models import Plan
from test_m7 import case, complete


def projection(root):
    store=WorkspaceStore([(None,root)])
    return store,store.open(store.catalog()[0].registration_id),Plan.model_validate_json((root/'workflow/plan.json').read_text())


def test_all_rows_exact_and_immutable_publication(case):
    options,_=complete(case);root=options['output'];before=snapshot(root)
    store=WorkspaceStore([])
    view=store.register_completed('New analysis',root,finalize=True)
    assert snapshot(root)=={**before,FILENAME:snapshot(root)[FILENAME]}
    assert FILENAME in store.opened[view.workspace_id].identity
    assert store.get(view.workspace_id).view==view
    workbook=load_workbook(root/FILENAME)
    assert workbook.sheetnames==['Summary','Definitions']
    assert [c.value for c in workbook['Summary'][1]]==HEADERS
    plan=Plan.model_validate_json((root/'workflow/plan.json').read_text())
    for row,sample in zip(list(workbook['Summary'].iter_rows())[1:],plan.samples):
        assert [c.value for c in row[:2]]==[sample['sample_name'],sample['barcode_id']]
        for column,metric in [(2,'target_crispresso_native_pe'),(4,'total_precise_pe')]:
            value=next(o for o in view.observations if o.sample_id==sample['barcode_id'] and o.metric_name==metric and o.copy_name is None)
            if value.status=='REPORTABLE':
                assert row[column].value==pytest.approx(value.fraction)
                assert row[column].number_format=='0.00%'
                assert row[column+1].value==f'{value.numerator} / {value.denominator}'
            else:assert row[column].value==row[column+1].value=='Not available'
    assert 'NOT Modified%' in workbook['Definitions']['B5'].value
    workbook.close()
    # A later historical-style open is read-only, even within the same release.
    after=snapshot(root);store.open(store.catalog()[0].registration_id);assert snapshot(root)==after


@pytest.mark.parametrize('status',['REPORTABLE','BLOCKED','NOT_ASSESSABLE'])
def test_large_counts_zero_background_and_formula_safe_strings(tmp_path,status):
    huge=2**53+1
    source=SimpleNamespace(name='metrics/result.json',sha256='a'*64)
    def observation(sample,metric):
        return SimpleNamespace(sample_id=sample,metric_name=metric,copy_name=None,routing_conditioned=False,
            target='ALSW',status=status,numerator=str(huge) if sample=='1A' else '0',denominator=str(huge+11),
            fraction=huge/(huge+11) if sample=='1A' else 0.0,source=source)
    view=SimpleNamespace(mode='precise_edit',targets=['ALSW'],label='Example',snapshot_id='b'*64,
        observations=[observation(s,m) for s in ['1A','2A'] for m in ['target_crispresso_native_pe','total_precise_pe']])
    plan=SimpleNamespace(samples=[{'sample_name':'=HYPERLINK("bad")','barcode_id':'1A'},{'sample_name':'EV','barcode_id':'2A'}])
    write_summary(tmp_path,view,plan)
    book=load_workbook(tmp_path/FILENAME);sheet=book['Summary']
    assert sheet['A2'].data_type=='s'
    if status=='REPORTABLE':
        assert sheet['D2'].value==f'{huge} / {huge+11}'
        assert sheet['C3'].value==0
        assert sheet['D3'].value==f'0 / {huge+11}'
    else:assert sheet['C2'].value==sheet['D3'].value=='Not available'
    book.close()


def test_atomic_failure_leaves_no_final_or_temp(case,monkeypatch):
    options,_=complete(case);root=options['output'];_,view,plan=projection(root)
    def fail(*args):raise OSError('disk full')
    monkeypatch.setattr('openpyxl.workbook.workbook.Workbook.save',fail)
    with pytest.raises(OSError):write_summary(root,view,plan)
    assert not (root/FILENAME).exists()
    assert not list(root.glob('.peanalyzer-summary-*'))


def test_existing_destination_never_overwritten(case):
    options,_=complete(case);root=options['output'];_,view,plan=projection(root)
    p=root/FILENAME;p.write_bytes(b'foreign')
    with pytest.raises(ValueError):write_summary(root,view,plan)
    assert p.read_bytes()==b'foreign'


def test_original_csv_order_and_existing_summary_validation(case):
    options,_=case
    path=options['samples'];lines=path.read_text().splitlines()
    path.write_text('\n'.join([lines[0],*reversed(lines[1:])])+'\n')
    options,_=complete(case);root=options['output']
    store=WorkspaceStore([]);view=store.register_completed('New',root,finalize=True)
    book=load_workbook(root/FILENAME)
    assert book['Summary']['B2'].value=='bc002'
    book['Summary']['D2']='fabricated'
    book.save(root/FILENAME);book.close()
    with pytest.raises(ValueError):WorkspaceStore([]).register_completed('New',root,finalize=True)
