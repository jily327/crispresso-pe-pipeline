"""Executable baseline oracles, using current backend authority, not new validators."""
import copy, csv, gzip, hashlib, json, shutil, sys
from pathlib import Path
from typing import get_args
import pytest
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(ROOT/'tests')]
from audit_tools import tripwire,version_sources
from peanalyzer.barcodes import bundled_catalog,load_catalog
from peanalyzer.gui.setup_validation import MemoryCSV,compile_draft
from peanalyzer.gui.setup_models import DraftContent,PETargetDraft
from peanalyzer.gui.drafts import SetupReferences
from peanalyzer.gui.job_models import JobState,StageState
from peanalyzer.gui.projection import ratio
from types import SimpleNamespace
from peanalyzer.schemas import Sample
from peanalyzer.validation import load_samples
from m7_fixtures import fixture

def catalog_sample(catalog):
    # 4A is a sample ID on main, NOT an implicit barcode mapping.
    return catalog.resolve_sample(Sample(sample_name='sample1',barcode_id='4A',forward_barcode_id='F4',reverse_barcode_id='RA',editor='editorA',treatment='control',dpi=6,biological_replicate='01',paired=False))

def test_catalog_authority_and_perturbation():
    c=load_catalog(bundled_catalog());s=catalog_sample(c)
    assert s.forward_barcode==c.ends['forward']['F4'] and s.reverse_barcode==c.ends['reverse']['RA']
    c.ends['forward']['F4']='ACGTACGTA'
    assert catalog_sample(c).forward_barcode=='ACGTACGTA'

def test_manual_excel_semantic_oracle():
    row=catalog_sample(load_catalog(bundled_catalog())).model_dump()
    manual=load_samples(MemoryCSV([row],'manual'),load_catalog(bundled_catalog()))
    excel={k:(' '+str(v)+' ' if isinstance(v,str) else '' if v is None else v) for k,v in row.items()}
    imported=load_samples(MemoryCSV([excel],'excel cell values'),load_catalog(bundled_catalog()))
    assert [s.model_dump() for s in manual]==[s.model_dump() for s in imported]

def test_identity_oracle(tmp_path):
    paths=fixture(tmp_path/'legacy',samples=1,copies=1)
    samples=list(csv.DictReader(paths['samples'].open()))
    for s in samples:s['paired']=False
    targets=[{k:v for k,v in r.items() if k in PETargetDraft.model_fields} for r in csv.DictReader(paths['targets'].open())]
    def compile_at(directory,renamed=False,name='Audit',output=None):
        directory.mkdir(exist_ok=True)
        files=[]
        for mate in ('r1','r2'):
            dest=directory/(('opaque-'+mate+'.fastq.gz') if renamed else paths[mate].name)
            if dest!=paths[mate]:shutil.copyfile(paths[mate],dest)
            files.append(dest)
        refs=SetupReferences(files,output_roots=[output] if output else [])
        ids=list(refs.entries)
        content=DraftContent(analysis_name=name,r1=ids[0],r2=ids[1],samples=samples,targets=targets,analysis_mode='precise_edit',library_profile='custom',trim_r1='8',trim_r2='8',output_root=ids[2] if output else None,workspace_name='run' if output else '')
        r=compile_draft(content,1,refs,());assert r.status=='VALID',r.issues
        return r
    legacy=compile_at(tmp_path/'legacy');same=compile_at(tmp_path/'staged');renamed=compile_at(tmp_path/'renamed',True)
    assert legacy._compiled==same._compiled
    assert legacy.preview.scientific_identity_sha256==same.preview.scientific_identity_sha256
    assert legacy.preview.plan_identity_sha256==same.preview.plan_identity_sha256
    assert renamed.preview.scientific_identity_sha256!=legacy.preview.scientific_identity_sha256
    x=copy.deepcopy(legacy._compiled['science']);y=copy.deepcopy(renamed._compiled['science'])
    for role in ('r1','r2'):x['inputs'][role].pop('name');y['inputs'][role].pop('name')
    assert x==y
    for root in ('out1','out2'):(tmp_path/root).mkdir()
    a=compile_at(tmp_path/'legacy',output=tmp_path/'out1');b=compile_at(tmp_path/'legacy',output=tmp_path/'out2')
    assert a.preview.scientific_identity_sha256==b.preview.scientific_identity_sha256
    assert a.preview.plan_identity_sha256!=b.preview.plan_identity_sha256

def test_lifecycle_enums():
    assert set(get_args(JobState))=={'STARTING','RUNNING','CANCELLING','CANCELLED','FAILED','COMPLETED'}
    assert set(get_args(StageState))=={'PENDING','RUNNING','COMPLETED','SKIPPED_SCIENTIFIC_GATE','REUSED','FAILED','CANCELLED'}

def test_null_and_large_integer_projection():
    assert ratio(SimpleNamespace(numerator=None,denominator=None,fraction=None))==dict(numerator=None,denominator=None,fraction=None,percentage=None)
    n=2**53+1;out=ratio(SimpleNamespace(numerator=n,denominator=n+2,fraction=0.9999999999999998));assert out['numerator']==str(n) and out['denominator']==str(n+2)

def test_baseline_tripwire():assert tripwire(ROOT)==[]
def test_tripwire_catches_mutation(tmp_path):
    p=tmp_path/'src/peanalyzer';p.mkdir(parents=True);f=p/'routing.py';f.write_text('changed')
    manifest={'files':{'src/peanalyzer/routing.py':{'sha256':'0'*64,'policy':'BYTE_IDENTICAL'}}}
    assert tripwire(tmp_path,manifest)==[{'path':'src/peanalyzer/routing.py','disposition':'BYTE_IDENTICAL'}]

def test_baseline_version():assert version_sources(ROOT,'0.8.0')['project']=='0.8.0'

def test_fixture_hashes_and_truncation():
    f=HERE/'fixtures'
    for name,entry in json.loads((f/'manifest.json').read_text()).items():
        p=f/name;assert hashlib.sha256(p.read_bytes()).hexdigest()==entry['sha256'];assert p.stat().st_size==entry['size_bytes']
    assert gzip.decompress((f/'R1.fastq.gz').read_bytes()).count(b'@audit')==16
    with pytest.raises((EOFError,OSError)):gzip.decompress((f/'truncated.fastq.gz').read_bytes())

@pytest.mark.parametrize('terminal',['FAILED','CANCELLED','COMPLETED'])
def test_final_verification_is_presentation_only(terminal):
    import threading
    from peanalyzer.gui.jobs import JobStore
    store=JobStore.__new__(JobStore);store.lock=threading.RLock();events=[]
    store._event=lambda job,status,**kw:events.append(status)
    stage=SimpleNamespace(stage_id='report',status='RUNNING',reason_codes=[])
    view=SimpleNamespace(state='RUNNING',stages=[stage],current_stage_id='report',finished_stages=0)
    job=SimpleNamespace(view=view,cancel=threading.Event())
    store._observe(job,{'status':'COMPLETED','stage_id':'report'})
    assert view.state=='RUNNING' and view.finished_stages==1
    store._observe(job,{'status':'FINAL_VALIDATION'})
    assert view.state=='RUNNING' and view.current_stage_id is None and view.finished_stages==1
    view.state=terminal;previous=list(events)
    store._observe(job,{'status':'WORKER_READY'})
    assert view.state==terminal and events==previous

def test_display_fixture_shapes():
    from peanalyzer.gui.models import Observation
    scenarios=json.loads((HERE/'fixtures/metric-display.json').read_text())['scenarios']
    for rows in scenarios.values():
        for row in rows:assert Observation.model_validate(row).model_dump()==row
    normal=scenarios['normal']
    assert {'total_precise_pe','target_crispresso_native_pe'}<={r['metric_name'] for r in normal}
    assert {'chr01','chr11'}<={r['copy_name'] for r in normal}
