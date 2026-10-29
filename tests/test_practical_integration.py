"""Native Core scientific parity: legacy/manual versus uploaded/XLSX inputs."""
import json
import os
from pathlib import Path
import pytest
from m11b_helpers import application,reviewed,wait_for
from test_m11b_integration import full_science
from test_practical_parity import uploaded,imported
from peanalyzer.gui.setup_models import DraftContent
from peanalyzer.workflow import verify_workflow_output
from peanalyzer.workflow_storage import digest

pytestmark=[pytest.mark.crispresso_integration,pytest.mark.skipif(os.environ.get('M11B_INTEGRATION')!='1',reason='requires qualified native Core 2.3.4')]

@pytest.mark.parametrize('mode',['precise_edit','indel_nuclease'])
def test_real_transport_scientific_parity(tmp_path,mode):
    root=Path(os.environ.get('PRACTICAL_RESULTS_DIR',tmp_path))/mode
    app,c,content,options,out=application(root,mode);app.state.uploads.root=root/'uploads'
    try:
        legacy=c.post('/api/v1/jobs',json=reviewed(c,content));assert legacy.status_code==200,legacy.text
        first=wait_for(c,legacy.json()['job_id'],timeout=180);assert first['state']=='COMPLETED',first
        rows=imported(c,content);r1=uploaded(c,options['r1']);r2=uploaded(c,options['r2'])
        other=DraftContent.model_validate({**content.model_dump(),'workspace_name':'uploaded','r1':r1['file_id'],'r2':r2['file_id'],'samples':rows})
        submitted=c.post('/api/v1/jobs',json=reviewed(c,other));assert submitted.status_code==200,submitted.text
        second=wait_for(c,submitted.json()['job_id'],timeout=180);assert second['state']=='COMPLETED',second
        a,b=out/'analysis',out/'uploaded'
        assert verify_workflow_output(a).status==verify_workflow_output(b).status=='COMPLETED'
        assert full_science(a)==full_science(b)
        assert (b/'statistics/result.json').read_bytes()==(b/'report/source/result.json').read_bytes()
        av=c.get('/api/v1/workspaces/'+first['workspace_id']).json();bv=c.get('/api/v1/workspaces/'+second['workspace_id']).json()
        def values(v):return [{k:o[k] for k in ('sample_id','target','metric_name','copy_name','numerator','denominator','fraction','percentage','status','reasons','label','numerator_label','denominator_label','definition')} for o in v['observations']]
        assert values(av)==values(bv)
        if mode=='precise_edit':
            native=next(o for o in bv['observations'] if o['metric_name']=='target_crispresso_native_pe')
            assert native['label']=='CRISPResso Prime-edited reference fraction'
            assert 'not CRISPResso Modified%' in native['definition']
        (root/'parity.json').write_text(json.dumps({'mode':mode,'legacy_state':first['state'],'uploaded_state':second['state'],'science_sha256':digest(full_science(a)),'uploaded_science_sha256':digest(full_science(b)),'source_report_bytes_equal':True,'observations_equal':True,'provenance_differences':['input basename/path','output-root-bound identities','source result hashes','timestamps','invocation']},indent=2)+'\n')
    finally:app.state.jobs.close()
