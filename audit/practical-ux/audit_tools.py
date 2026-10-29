"""Read-only checks. A review-required difference is never an automatic pass."""
import argparse, ast, hashlib, json, subprocess, sys, tomllib, zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
BASE='72e0f86a495e079cab2ae50d2796e7a3423c78af'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def tripwire(root,manifest=None):
    m=manifest or json.loads((HERE/'frozen-core.json').read_text());findings=[]
    for name,record in m['files'].items():
        path=root/name
        if not path.is_file() or path.is_symlink() or sha(path)!=record['sha256']:
            findings.append({'path':name,'disposition':record['policy']})
    known=set(m['files'])
    for path in sorted((root/'src/peanalyzer').rglob('*')):
        if path.is_file() and path.suffix in {'.py','.yaml','.csv','.json'} and 'static' not in path.parts and path.relative_to(root).as_posix() not in known:
            findings.append({'path':path.relative_to(root).as_posix(),'disposition':'REVIEW_NEW_PRODUCTION_FILE'})
    return findings

def version_sources(root,expected,wheel=None):
    project=tomllib.loads((root/'pyproject.toml').read_text())['project']['version']
    tree=ast.parse((root/'src/peanalyzer/__init__.py').read_text())
    node=next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='__version__' for t in n.targets))
    if isinstance(node,ast.Call):
        assert ast.unparse(node)=="version('crispresso-pe-pipeline')", 'Review changed runtime version authority'
        runtime=project  # source authority only; installed runtime is checked separately
    else:runtime=ast.literal_eval(node)
    values={'project':project,'runtime_source':runtime,'frontend':json.loads((root/'frontend/package.json').read_text())['version']}
    lock=json.loads((root/'frontend/package-lock.json').read_text());values['npm_lock']=lock['version'];values['npm_root']=lock['packages']['']['version']
    if wheel:
        with zipfile.ZipFile(wheel) as z:
            metadata=[n for n in z.namelist() if n.endswith('.dist-info/METADATA')];assert len(metadata)==1
            values['wheel']=next(l.split(': ',1)[1] for l in z.read(metadata[0]).decode().splitlines() if l.startswith('Version: '))
    assert all(v==expected for v in values.values()),values
    return values

def freeze(root):
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==BASE
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE],cwd=root,text=True).splitlines()
    records={}
    shared={'app.py','__main__.py','drafts.py','setup_models.py','setup_validation.py','models.py','projection.py','job_models.py','jobs.py'}
    for name in names:
        policy=None
        if name.startswith('src/peanalyzer/'):
            policy='BYTE_IDENTICAL'
            if '/gui/static/' in name:policy='REVIEW_REGENERATED_BUNDLE'
            elif name=='src/peanalyzer/__init__.py':policy='VERSION_ONLY'
            elif '/gui/' in name and Path(name).name in shared:policy='REVIEW_NARROW_ADDITIVE_CHANGE'
        elif name.startswith('docs/validation/') or name.startswith('frontend/src/tests/fixtures/'):policy='HISTORICAL_BYTE_IDENTICAL'
        elif name in ('pyproject.toml','frontend/package.json','frontend/package-lock.json','viewer_build.py','setup.py') or name.startswith('frontend/src/models/'):policy='REVIEW_VERSION_OR_PRESENTATION'
        if policy:records[name]={'sha256':sha(root/name),'policy':policy}
    (HERE/'frozen-core.json').write_text(json.dumps({'base_main':BASE,'files':records},indent=2)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','tripwire','version']);p.add_argument('--root',type=Path,default=HERE.parents[1]);p.add_argument('--expected',default='0.9.0');p.add_argument('--wheel',type=Path);a=p.parse_args()
    if a.command=='freeze':freeze(a.root)
    elif a.command=='tripwire':
        results=tripwire(a.root);print(json.dumps(results,indent=2));sys.exit(bool(results))
    else:print(json.dumps(version_sources(a.root,a.expected,a.wheel),indent=2))
