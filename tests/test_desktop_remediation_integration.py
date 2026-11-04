"""Real Core release checks at the optional export boundary, serialized by pytest."""
import os
import pytest
from openpyxl import load_workbook
from m11b_helpers import application, reviewed, wait_for
from peanalyzer.gui.setup_models import DraftContent
from peanalyzer.gui.summary_workbook import FILENAME
from peanalyzer.workflow import verify_workflow_output

pytestmark=[pytest.mark.crispresso_integration,pytest.mark.skipif(os.environ.get('M11B_INTEGRATION')!='1',reason='requires qualified native Core 2.3.4')]


def test_real_scientific_completion_survives_partial_export_write(tmp_path,monkeypatch):
    app,client,content,_,out=application(tmp_path/'export-failure')
    def fail(self,stream):
        stream.write(b'partial workbook')
        raise OSError('simulated export disk failure')
    monkeypatch.setattr('openpyxl.workbook.workbook.Workbook.save',fail)
    try:
        response=client.post('/api/v1/jobs',json=reviewed(client,content))
        assert response.status_code==200,response.text
        job=wait_for(client,response.json()['job_id'],timeout=180)
        assert job['state']=='COMPLETED' and job['error'] is None,job
        root=out/'analysis'
        assert verify_workflow_output(root).status=='COMPLETED'
        view=client.get('/api/v1/workspaces/'+job['workspace_id'])
        assert view.status_code==200 and view.json()['verified']
        exact=next(o for o in view.json()['observations'] if o['metric_name']=='total_precise_pe')
        assert (exact['numerator'],exact['denominator'])==('2','24')
        export=client.get('/api/v1/workspaces/'+job['workspace_id']+'/export').json()
        assert export['state']=='MISSING' and 'Optional Excel export' in export['warning']
        assert not (root/FILENAME).exists() and not list(root.glob('.peanalyzer-summary-*'))
    finally:app.state.jobs.close()


def test_real_job_preserves_accepted_gui_order_without_changing_canonical_plan(tmp_path,monkeypatch):
    import m11b_helpers
    original=m11b_helpers.fixture
    monkeypatch.setattr(m11b_helpers,'fixture',lambda root,**kw:original(root,**{**kw,'samples':2}))
    app,client,content,_,out=application(tmp_path/'ordering')
    content=DraftContent.model_validate({**content.model_dump(),'samples':[s.model_dump() for s in reversed(content.samples)]})
    expected=[s.barcode_id for s in content.samples]
    try:
        response=client.post('/api/v1/jobs',json=reviewed(client,content))
        assert response.status_code==200,response.text
        job=wait_for(client,response.json()['job_id'],timeout=180)
        assert job['state']=='COMPLETED',job
        import json
        plan=json.loads((out/'analysis/workflow/plan.json').read_text())
        assert [s['barcode_id'] for s in plan['samples']]==sorted(expected)
        book=load_workbook(out/'analysis'/FILENAME)
        assert [row[1] for row in list(book['Summary'].values)[1:]]==expected
        book.close()
        assert client.get('/api/v1/workspaces/'+job['workspace_id']+'/export').json()['state']=='UNCHANGED'
    finally:app.state.jobs.close()
