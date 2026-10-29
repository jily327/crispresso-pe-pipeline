"""Browser transport is bounded and never a second scientific executor."""
import asyncio
import gzip
import hashlib
from pathlib import Path
import tracemalloc

import pytest
from fastapi.testclient import TestClient
from peanalyzer.gui.app import create_app
from peanalyzer.gui.drafts import SetupReferences
from peanalyzer.gui.uploads import UploadStore
from peanalyzer.gui.workspace import ViewerError

RAW=b'@read/1\nACGT\n+\nIIII\n'

@pytest.fixture
def api(tmp_path):
    legacy=tmp_path/'legacy.fastq';legacy.write_bytes(RAW)
    app=create_app(token='test',setup_files=[legacy],upload_root=tmp_path/'uploads')
    with TestClient(app,base_url='http://127.0.0.1',headers={'X-Viewer-Token':'test'}) as client:
        yield app,client,legacy
    assert legacy.read_bytes()==RAW


def upload(client,data,name='R1.fastq.gz',**kwargs):
    return client.post('/api/v1/setup/uploads/fastq',params={'filename':name},content=data,
                       headers={'Content-Type':'application/octet-stream',**kwargs})


@pytest.mark.parametrize('name',['R1.fastq.gz','R2.fastq.gz','same.fastq.gz','../../escape.fastq.gz','/tmp/absolute.fastq.gz',r'C:\Users\sample.fastq.gz'])
def test_bytes_names_and_replacement(api,name):
    app,client,legacy=api;raw=gzip.compress(RAW,mtime=0)
    first=upload(client,raw,name);assert first.status_code==200,first.text
    a=first.json();b=upload(client,raw,name).json();assert a['file_id']!=b['file_id']
    refs=app.state.drafts.references
    for entry in (a,b):
        path=refs.resolve(entry['file_id'],'fastq');assert path.parent.parent==app.state.uploads.root
        assert path.name=='input.fastq.gz' and path.read_bytes()==raw
        assert entry['sha256']==hashlib.sha256(raw).hexdigest() and entry['size_bytes']==str(len(raw))
        assert entry['label']==name
    # Registration does not silently patch any draft or execute anything.
    d=client.post('/api/v1/drafts').json();assert d['content']['r1'] is None
    assert client.get('/api/v1/jobs').json()==[]


@pytest.mark.parametrize('data,name',[(b'','x.fastq'),(b'not gzip','x.fastq.gz'),(b'no reads','x.fastq'),(RAW,'x.txt'),(b'/etc/passwd','x.fastq.gz'),(gzip.compress(b''),'x.fastq.gz'),(gzip.compress(RAW)[:-5],'x.fastq.gz')])
def test_failed_upload_never_registers(api,data,name):
    app,client,_=api;n=len(app.state.drafts.references.entries)
    r=upload(client,data,name);assert r.status_code==409,r.text
    assert len(app.state.drafts.references.entries)==n
    assert not app.state.uploads.root.exists() or list(app.state.uploads.root.iterdir())==[]


@pytest.mark.parametrize('headers,status',[({'X-Viewer-Token':''},401),({'Origin':'http://evil.invalid'},403),({'Host':'evil.invalid'},403)])
def test_upload_uses_existing_boundary(api,headers,status):
    app,client,_=api
    assert upload(client,gzip.compress(RAW),**headers).status_code==status
    assert not app.state.uploads.root.exists()


class Request:
    headers={'content-type':'application/octet-stream'}
    def __init__(self,blocks,fail=False):self.blocks=blocks;self.fail=fail
    async def stream(self):
        for b in self.blocks:yield b
        if self.fail:raise asyncio.CancelledError()


def test_interrupted_cleanup(tmp_path):
    refs=SetupReferences();store=UploadStore(tmp_path/'uploads',refs)
    with pytest.raises(asyncio.CancelledError):asyncio.run(store.receive(Request([RAW],True),'x.fastq'))
    assert not refs.entries and list(store.root.iterdir())==[]


def test_symlink_root_refused(tmp_path):
    outside=tmp_path/'outside';outside.mkdir();link=tmp_path/'uploads';link.symlink_to(outside,target_is_directory=True)
    with pytest.raises(ValueError):asyncio.run(UploadStore(link,SetupReferences()).receive(Request([RAW]),'x.fastq'))
    assert list(outside.iterdir())==[]


def test_registration_failure_cleanup(tmp_path,monkeypatch):
    refs=SetupReferences();store=UploadStore(tmp_path/'uploads',refs)
    def fail(*a):raise ViewerError('TEST_FAIL','Injected registration failure')
    monkeypatch.setattr(refs,'register_upload',fail)
    with pytest.raises(ViewerError):asyncio.run(store.receive(Request([RAW]),'x.fastq'))
    assert list(store.root.iterdir())==[] and not refs.entries


def test_bounded_streaming(tmp_path):
    # 12+ MB generated lazily, well above allowed application-buffer overhead.
    block=RAW*4096;count=160
    store=UploadStore(tmp_path/'uploads',SetupReferences())
    tracemalloc.start()
    row=asyncio.run(store.receive(Request((block for _ in range(count))),'large.fastq'))
    _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    assert int(row.size_bytes)==len(block)*count>10*1024**2
    assert peak<6*1024**2


def test_transport_size_and_type(api):
    app,client,_=api
    assert upload(client,RAW,'x.fastq',**{'Content-Length':'1'}).status_code==409
    assert upload(client,RAW,'x.fastq',**{'Content-Type':'application/json'}).status_code==409
    assert not app.state.uploads.root.exists() or list(app.state.uploads.root.iterdir())==[]


def test_upload_mutation_detected(api):
    app,client,_=api;entry=upload(client,RAW,'x.fastq').json();refs=app.state.drafts.references
    path=refs.resolve(entry['file_id'],'fastq');path.chmod(0o600);path.write_bytes(RAW+RAW)
    with pytest.raises(ViewerError,match='UPLOAD_CHANGED'):refs.identity(entry['file_id'])
