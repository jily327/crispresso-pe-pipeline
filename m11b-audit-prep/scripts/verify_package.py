"""Verify frozen package payload and ZIP, rejecting unexpected files/symlinks."""
import argparse,hashlib,json,zipfile
from pathlib import Path
from common import read,sha
EXCLUDED={'CHECKSUMS.json','peanalyzer-m11b-audit-prep.zip','ARCHIVE_SHA256.txt'}
def verify(root):
    root=Path(root);manifest=read(root/'CHECKSUMS.json');expected=manifest['files']
    found={}
    for p in root.rglob('*'):
        if p.is_symlink():raise ValueError('package symlink')
        if p.is_file() and p.relative_to(root).as_posix() not in EXCLUDED:
            found[p.relative_to(root).as_posix()]={'sha256':sha(p),'size_bytes':p.stat().st_size}
    assert found==expected,'payload inventory/hash mismatch'
    archive=root/'peanalyzer-m11b-audit-prep.zip'
    assert sha(archive)==(root/'ARCHIVE_SHA256.txt').read_text().split()[0],'ZIP hash mismatch'
    with zipfile.ZipFile(archive) as z:
        names=z.namelist();assert len(names)==len(set(names)),'duplicate ZIP entry'
        wanted=set(expected)|{'CHECKSUMS.json'};assert set(names)==wanted,'ZIP inventory mismatch'
        for name in names:assert z.read(name)==(root/name).read_bytes(),'ZIP byte mismatch: '+name
        assert z.testzip() is None
    return {'payload_files':len(expected),'archive_entries':len(names),'payload_and_archive_bytes':'MATCH'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');a=p.parse_args();print(json.dumps(verify(a.root),indent=2))
