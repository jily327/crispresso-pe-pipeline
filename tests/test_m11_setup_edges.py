"""Input archive, filesystem and validation race boundaries for setup."""
import copy
import csv
import gzip
import json
import pytest
from peanalyzer.gui.drafts import DraftStore, SetupReferences
from peanalyzer.gui.setup_models import DraftContent, DraftPatch, PETargetDraft, DraftSample
from peanalyzer.gui.workspace import ViewerError
from peanalyzer.workflow_storage import WorkflowError
from peanalyzer.backend.synthetic import design
from gui_helpers import forbid_execution
from test_demux_verify import completed
from test_m11_setup import setup, validate, inventory


@pytest.mark.parametrize('mutation',['none','bad_trim','changed_barcode','tampered'])
def test_verified_archive_uses_real_verifier(completed,example_dir,monkeypatch,mutation):
    raw=json.loads((completed/'01_demux_QC/demux_summary.json').read_text())['samples']
    samples=[dict({k:v for k,v in row.items() if k in DraftSample.model_fields},editor='fixture-editor',treatment='fixture-treatment',dpi='6',biological_replicate=str(i+1),paired=False) for i,row in enumerate(raw)]
    targets=[{k:'' if v is None else v for k,v in row.items() if k in PETargetDraft.model_fields} for row in design()['targets']]
    refs=SetupReferences(archives=[completed]);store=DraftStore(refs)
    data=DraftContent(analysis_name='Archive preview',input_mode='analyze',demux=next(iter(refs.entries)),samples=samples,analysis_mode='precise_edit',targets=targets)
    if mutation=='bad_trim':data.trim_r1=data.trim_r2='10000'
    if mutation=='changed_barcode':data.samples[0].forward_barcode='ACGTACGT'
    if mutation=='tampered':(completed/'02_demultiplexed_fastq/1B_R1.fastq.gz').write_bytes(b'broken')
    before=inventory(completed);calls=forbid_execution(monkeypatch)
    d=store.create();d=store.patch(d.draft_id,DraftPatch(revision=0,content=data));r=store.validate(d.draft_id,1)
    assert r.status==('VALID' if mutation=='none' else 'INVALID')
    if mutation=='none':
        assert r.preview.source_mode=='analyze'
        assert r.preview.stages[0].kind!='demux'
        assert store.preview(d.draft_id,1)==r.preview
    assert not calls and inventory(completed)==before


@pytest.mark.parametrize('mutation',['unsynchronized','malformed','missing'])
def test_raw_input_format_and_presence(setup,mutation):
    _,_,paths,_=setup
    if mutation=='missing':paths['r2'].unlink()
    elif mutation=='malformed':paths['r2'].write_bytes(b'not gzip')
    else:
        raw=gzip.decompress(paths['r2'].read_bytes()).replace(b'@bc001_',b'@other_',1)
        paths['r2'].write_bytes(gzip.compress(raw,mtime=0))
    _,r=validate(setup);assert r.status=='INVALID' and not r.preview


def test_proposed_destination_cannot_be_inside_protected_workspace(setup):
    store,data,_,output=setup;store.protected=(output,)
    data=copy.deepcopy(data);data['output_root']=next(k for k,v in store.references.entries.items() if v.kind=='output_root');data['workspace_name']='nested'
    _,r=validate(setup,data);assert r.status=='INVALID' and not (output/'nested').exists()


def test_change_during_revalidation_removes_previous_valid_snapshot(setup,monkeypatch):
    store,data,paths,_=setup;d,r=validate(setup);assert r.status=='VALID'
    import peanalyzer.gui.drafts as module
    original=module.compile_draft
    def racing(*a,**k):
        result=original(*a,**k);paths['r1'].write_bytes(b'changed after validation');return result
    monkeypatch.setattr(module,'compile_draft',racing)
    with pytest.raises(ViewerError,match='DRAFT_INPUT_CHANGED'):store.validate(d.draft_id,1)
    assert store.get(d.draft_id).validation is None
    with pytest.raises(ViewerError,match='DRAFT_NOT_VALIDATED'):store.preview(d.draft_id,1)


def test_output_registration_rejects_symlink(tmp_path):
    real=tmp_path/'real';real.mkdir();alias=tmp_path/'alias';alias.symlink_to(real,target_is_directory=True)
    with pytest.raises(WorkflowError,match='UNSAFE_PATH'):SetupReferences(output_roots=[alias])
