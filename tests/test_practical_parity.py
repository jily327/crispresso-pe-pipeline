"""Transport adapters preserve the existing compiler, including provenance-sensitive names."""
import copy
from m11b_helpers import application,reviewed
from test_practical_workbook import workbook
from peanalyzer.gui.setup_models import DraftContent
from peanalyzer.workflow_storage import digest


def uploaded(client,path,name=None):
    r=client.post('/api/v1/setup/uploads/fastq',params={'filename':name or path.name},content=path.read_bytes(),headers={'Content-Type':'application/octet-stream'})
    assert r.status_code==200,r.text
    return r.json()


def imported(client,content):
    r=client.post('/api/v1/setup/samples/import?profile=custom',content=workbook([s.model_dump() for s in content.samples]),headers={'Content-Type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})
    assert r.status_code==200 and not r.json()['errors'],r.text
    return r.json()['samples']


def test_compiled_legacy_upload_import_equivalence(tmp_path):
    app,c,content,options,out=application(tmp_path)
    app.state.uploads.root=tmp_path/'uploads'
    before=reviewed(c,content);a=app.state.drafts.get(before['draft_id']).validation._compiled
    rows=imported(c,content)
    r1=uploaded(c,options['r1']);r2=uploaded(c,options['r2'])
    other=DraftContent.model_validate({**content.model_dump(),'r1':r1['file_id'],'r2':r2['file_id'],'samples':rows})
    after=reviewed(c,other);b=app.state.drafts.get(after['draft_id']).validation._compiled
    assert a['files']==b['files']
    aa,bb=copy.deepcopy(a['science']),copy.deepcopy(b['science'])
    for role,entry in [('r1',r1),('r2',r2)]:
        assert aa['inputs'][role]['sha256']==bb['inputs'][role]['sha256']==entry['sha256']
        assert aa['inputs'][role]['size_bytes']==bb['inputs'][role]['size_bytes']==entry['size_bytes']
        aa['inputs'][role].pop('name');bb['inputs'][role].pop('name')
    assert aa==bb
    assert before['scientific_identity_sha256']!=after['scientific_identity_sha256'] # source basename remains authoritative
    assert digest(a['science'])==before['scientific_identity_sha256']
    assert digest(b['science'])==after['scientific_identity_sha256']
    assert c.get('/api/v1/jobs').json()==[] and list(out.iterdir())==[]
    # Existing pairing validator, not the transport adapter, rejects swapped/mismatched mates.
    wrong=other.model_copy(update={'r2':r1['file_id']})
    d=c.post('/api/v1/drafts').json();c.patch('/api/v1/drafts/'+d['draft_id'],json={'revision':0,'content':wrong.model_dump()})
    assert c.post('/api/v1/drafts/'+d['draft_id']+'/validate',json={'revision':1}).json()['status']=='INVALID'
    app.state.jobs.close()


def test_same_basename_identity_remains_exact(tmp_path):
    app,c,content,options,out=application(tmp_path)
    app.state.uploads.root=tmp_path/'uploads';refs=app.state.drafts.references
    for role in ('r1','r2'):
        p=tmp_path/role/'input.fastq.gz';p.parent.mkdir();p.write_bytes(options[role].read_bytes())
        refs.paths[getattr(content,role)]=p
    a=reviewed(c,content)
    other=content.model_copy(update={role:uploaded(c,options[role])['file_id'] for role in ('r1','r2')})
    b=reviewed(c,other)
    assert a['scientific_identity_sha256']==b['scientific_identity_sha256']
    assert a['plan_identity_sha256']==b['plan_identity_sha256']
    app.state.jobs.close()
