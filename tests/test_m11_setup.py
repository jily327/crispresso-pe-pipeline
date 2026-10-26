"""Setup uses real metadata authorities and never scientific executors."""
import copy
import csv
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from peanalyzer.gui.app import create_app
from peanalyzer.gui.drafts import DraftStore, SetupReferences
from peanalyzer.gui.setup_models import DraftContent, DraftPatch, PETargetDraft
from peanalyzer.gui.workspace import ViewerError
from peanalyzer.schemas import reverse_complement
from peanalyzer.nuclease.targets import NucleaseTarget
from peanalyzer.workflow_storage import canonical
from m7_fixtures import fixture
from gui_helpers import forbid_execution


@pytest.fixture
def setup(tmp_path, monkeypatch):
    paths=fixture(tmp_path/'inputs',samples=2,copies=2)
    output=tmp_path/'outputs';output.mkdir()
    refs=SetupReferences([paths['r1'],paths['r2']],output_roots=[output])
    samples=list(csv.DictReader(paths['samples'].open()))
    for sample in samples:sample['paired']=False
    targets=[{k:v for k,v in row.items() if k in PETargetDraft.model_fields} for row in csv.DictReader(paths['targets'].open())]
    ids=list(refs.entries)
    data=DraftContent(analysis_name='Setup reference study',r1=ids[0],r2=ids[1],samples=samples,targets=targets,
        analysis_mode='precise_edit',library_profile='custom',trim_r1='8',trim_r2='8').model_dump()
    calls=forbid_execution(monkeypatch)
    def forbidden(*a,**k):
        calls.append('routing trial');raise AssertionError('Setup must not route even synthetic reads')
    monkeypatch.setattr('peanalyzer.routing.route_pair',forbidden)
    store=DraftStore(refs)
    yield store,data,paths,output
    assert not calls
    # Tests that intentionally mutate files assert their own expected inventory.


def inventory(root):
    return {str(p.relative_to(root)):(p.read_bytes(),p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}


def validate(setup,data=None):
    store,original,*_=setup
    d=store.create();d=store.patch(d.draft_id,DraftPatch(revision=0,content=DraftContent.model_validate(data or original)))
    return d,store.validate(d.draft_id,d.revision)


def nuclease(data,**changes):
    result=copy.deepcopy(data);result['analysis_mode']='indel_nuclease'
    result['targets']=[dict(analysis_mode='indel_nuclease',target_name='T1',copy_name='single',wt_sequence=data['targets'][0]['wt_sequence'],quantification_window_coordinates='0-0',**changes)]
    return result


def test_lifecycle_revisions_and_immutable_returns(setup):
    store,data,*_=setup
    d=store.create();assert d.revision==0 and d.content.analysis_mode is None
    d.content.analysis_name='Unstored';assert store.get(d.draft_id).content.analysis_name==''
    d=store.patch(d.draft_id,DraftPatch(revision=0,content=DraftContent(**data)))
    with pytest.raises(ViewerError,match='STALE_DRAFT_REVISION'):store.patch(d.draft_id,DraftPatch(revision=0,content=d.content))
    with pytest.raises(ViewerError,match='DRAFT_NOT_VALIDATED'):store.preview(d.draft_id,1)
    result=store.validate(d.draft_id,1);assert result.status=='VALID'
    result.preview.analysis_name='Unstored';assert store.preview(d.draft_id,1).analysis_name==data['analysis_name']
    store.patch(d.draft_id,DraftPatch(revision=1,content=d.content))
    with pytest.raises(ViewerError,match='STALE_DRAFT_REVISION'):store.preview(d.draft_id,1)
    with pytest.raises(ViewerError,match='DRAFT_NOT_VALIDATED'):store.preview(d.draft_id,2)
    store.delete(d.draft_id,2)
    with pytest.raises(ViewerError,match='DRAFT_NOT_FOUND'):store.get(d.draft_id)


def test_valid_pe_no_execution_or_file_writes(setup):
    store,data,paths,output=setup;before=inventory(output.parent)
    d,r=validate(setup);assert r.status=='VALID';p=store.preview(d.draft_id,d.revision)
    assert p.executable is False and p.copy_count=='2' and p.sample_ids==['bc001','bc002']
    assert any(a.name=='edits' for a in p.targets[0].annotation)
    assert inventory(output.parent)==before
    assert all('execute' not in node.kind for node in p.stages)


@pytest.mark.parametrize('window',['0-0','0-1_12-14','42-50'])
def test_explicit_nuclease_matches_authority(setup,window):
    data=nuclease(setup[1]);data['targets'][0]['quantification_window_coordinates']=window
    _,r=validate(setup,data);assert r.status=='VALID'
    config=r.targets[0].scientific_configuration
    assert len(config)==58
    target=NucleaseTarget.model_validate({k:v for k,v in data['targets'][0].items() if k!='profile'})
    assert {f.name:json.loads(f.value) for f in config}==target.scientific_identity['backend_settings']


@pytest.mark.parametrize('orientation',['forward','reverse'])
@pytest.mark.parametrize('window',['W1','W2','W3','W4'])
def test_tigr_backend_geometry(setup,orientation,window):
    data=nuclease(setup[1],profile='tigr_tas_v1',tigr_window=window)
    row=data['targets'][0];target=row['wt_sequence'][30:48]
    row['tigr_target_sequence']=target if orientation=='forward' else reverse_complement(target)
    row['quantification_window_coordinates']=''
    _,r=validate(setup,data);assert r.status=='VALID'
    annotation={f.name:json.loads(f.value) for f in r.targets[0].annotation}
    assert annotation==NucleaseTarget(analysis_mode='indel_nuclease',target_name='T1',copy_name='single',wt_sequence=row['wt_sequence'],nuclease_profile='tigr_tas_v1',tigr_window=window,tigr_target_sequence=row['tigr_target_sequence']).window
    assert annotation['orientation']==orientation and annotation['selected_window']==window


@pytest.mark.parametrize('window',['0','-1-5','3-2','0-999','1-3_2-4','', 'nan'])
def test_invalid_window_fails_closed(setup,window):
    data=nuclease(setup[1]);data['targets'][0]['quantification_window_coordinates']=window
    d,r=validate(setup,data);assert r.status=='INVALID' and r.preview is None
    assert any(i.field=='targets.0.quantification_window_coordinates' for i in r.issues)
    with pytest.raises(ViewerError):setup[0].preview(d.draft_id,d.revision)


@pytest.mark.parametrize('mutation',['missing','multiple','short','multi_copy'])
def test_invalid_tigr_or_copy_count(setup,mutation):
    data=nuclease(setup[1],profile='tigr_tas_v1',tigr_window='W2')
    row=data['targets'][0];row['quantification_window_coordinates']='';row['tigr_target_sequence']=row['wt_sequence'][30:48]
    if mutation=='missing':row['tigr_target_sequence']='A'*18
    if mutation=='short':row['tigr_target_sequence']='ACGT'
    if mutation=='multiple':row['wt_sequence']+=row['tigr_target_sequence']
    if mutation=='multi_copy':data['targets'].append(dict(row,copy_name='other'))
    _,r=validate(setup,data);assert r.status=='INVALID'


@pytest.mark.parametrize('mutation',['dna','same_product','missing_spacer','bad_extension','duplicate_copy','mode','two_targets'])
def test_invalid_pe_target(setup,mutation):
    data=copy.deepcopy(setup[1]);row=data['targets'][0]
    if mutation=='dna':row['wt_sequence']='ACGT!'
    if mutation=='same_product':row['prime_edited_sequence']=row['wt_sequence']
    if mutation=='missing_spacer':row['pegRNA_spacer']=''
    if mutation=='bad_extension':
        for t in data['targets']:t['pegRNA_extension']='A'*25
    if mutation=='duplicate_copy':data['targets'][1]['copy_name']=row['copy_name']
    if mutation=='mode':data['analysis_mode']='indel_nuclease'
    if mutation=='two_targets':data['targets'][1]['target_name']='other'
    _,r=validate(setup,data);assert r.status=='INVALID' and not r.preview


def test_pe_indel_reference_preview_does_not_route(setup):
    data=copy.deepcopy(setup[1])
    from peanalyzer.remediation import indel_designs
    targets=next(ts for design,ts in indel_designs() if design['id']=='insertion_12_seed11')
    data['targets']=[{k:'' if v is None else v for k,v in t.model_dump().items() if k in PETargetDraft.model_fields} for t in targets]
    _,r=validate(setup,data)
    assert r.targets and any('insertion' in f.value for f in r.targets[0].annotation if f.name=='edits')


@pytest.mark.parametrize('mutation',['r1','r2','same','unknown','duplicate','dpi','paired','name','trim','negative_trim','auto_custom'])
def test_invalid_sample_inputs_and_configuration(setup,mutation):
    data=copy.deepcopy(setup[1])
    if mutation in ('r1','r2'):data[mutation]=None
    if mutation=='same':data['r2']=data['r1']
    if mutation=='unknown':data['r1']='/etc/passwd'
    if mutation=='duplicate':data['samples'][1]['sample_name']=data['samples'][0]['sample_name']
    if mutation=='dpi':data['samples'][0]['dpi']='tomorrow'
    if mutation=='paired':data['samples'][0]['paired']=True
    if mutation=='name':data['samples'][0]['sample_name']='../escape'
    if mutation=='trim':data['trim_r1']=''
    if mutation=='negative_trim':data['trim_r1']='-1'
    if mutation=='auto_custom':data['trim_r1']=data['trim_r2']=''
    _,r=validate(setup,data);assert r.status=='INVALID'


def test_determinism_science_and_presentation_identity(setup):
    store,data,*_=setup;d,r=validate(setup)
    assert canonical(r)==canonical(store.validate(d.draft_id,d.revision))
    renamed=copy.deepcopy(data);renamed['analysis_name']='A different label'
    _,new=validate(setup,renamed)
    assert new.preview.scientific_identity_sha256==r.preview.scientific_identity_sha256
    assert new.preview.plan_identity_sha256!=r.preview.plan_identity_sha256
    changed=copy.deepcopy(data);changed['trim_r1']='9'
    _,new=validate(setup,changed)
    assert new.preview.scientific_identity_sha256!=r.preview.scientific_identity_sha256
    reordered=copy.deepcopy(data);reordered['samples'].reverse();reordered['targets'].reverse()
    _,new=validate(setup,reordered)
    assert canonical(new.preview)==canonical(r.preview)


@pytest.mark.parametrize('mutation',['deleted','changed','symlink'])
def test_input_identity_invalidation(setup,mutation):
    store,data,paths,_=setup;d,r=validate(setup);assert r.status=='VALID'
    if mutation=='deleted':paths['r1'].unlink()
    elif mutation=='changed':paths['r1'].write_bytes(b'changed')
    else:
        paths['r1'].unlink();paths['r1'].symlink_to(paths['r2'])
    with pytest.raises(ViewerError,match='DRAFT_INPUT_CHANGED'):store.preview(d.draft_id,d.revision)
    assert store.get(d.draft_id).validation is None


def test_output_proposal_is_never_created_and_invalidates_on_conflict(setup):
    store,data,_,output=setup;data=copy.deepcopy(data)
    data['output_root']=next(k for k,v in store.references.entries.items() if v.kind=='output_root');data['workspace_name']='proposed'
    d,r=validate(setup,data);assert r.status=='VALID' and not (output/'proposed').exists()
    (output/'proposed').mkdir()
    with pytest.raises(ViewerError,match='DRAFT_INPUT_CHANGED'):store.preview(d.draft_id,d.revision)
    _,r=validate(setup,data);assert r.status=='INVALID'


@pytest.mark.parametrize('name',['../escape','/absolute','bad/name',''])
def test_unsafe_output_name(setup,name):
    data=copy.deepcopy(setup[1]);data['output_root']=next(k for k,v in setup[0].references.entries.items() if v.kind=='output_root');data['workspace_name']=name
    _,r=validate(setup,data);assert r.status=='INVALID'


def test_new_routes_share_security_boundary(setup):
    _,_,paths,_=setup
    app=create_app(token='setup-token',setup_files=[paths['r1'],paths['r2']])
    with TestClient(app,base_url='http://127.0.0.1',headers={'X-Viewer-Token':'setup-token'}) as client:
        assert client.post('/api/v1/drafts',headers={'X-Viewer-Token':''}).status_code==401
        assert client.post('/api/v1/drafts',headers={'Origin':'https://evil.test'}).status_code==403
        assert client.post('/api/v1/drafts',headers={'Host':'evil.test'}).status_code==403
        caps=client.get('/api/v1/setup/capabilities').json()
        assert '/workspace' not in json.dumps(caps) and all(len(f['file_id'])==32 for f in caps['files'])
        d=client.post('/api/v1/drafts').json();base='/api/v1/drafts/'+d['draft_id']
        assert client.get(base).json()==d
        bad=copy.deepcopy(d);bad['content']['input_mode']='single_end'
        assert client.patch(base,json={'revision':0,'content':bad['content']}).status_code==422
        assert client.get(base+'/preview?revision=0').status_code==409
        assert client.delete(base+'?revision=0').status_code==204
        assert client.get(base).status_code==409
        assert client.get('/api/v1/files/etc/passwd').status_code==404


def test_generated_setup_contract_matches_python():
    from scripts.generate_viewer_types import generate
    from peanalyzer.gui import setup_models
    expected="import type { FieldValue } from './api';\n"+generate(setup_models)
    assert Path('frontend/src/models/setup.ts').read_text()==expected
