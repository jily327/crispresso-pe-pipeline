import hashlib,json,os,subprocess,tarfile,zipfile
from pathlib import Path
root=Path('/workspace/v1-desktop-qualification');repo=Path('/workspace/crispresso-pe-pipeline-v1');python=root/'source-env/bin/python'

def run(args,log,cwd=repo):
 with (root/log).open('w') as out:subprocess.run([str(x) for x in args],cwd=cwd,stdout=out,stderr=subprocess.STDOUT,check=True)
run([python,'-m','build','--no-isolation','--outdir',root/'dist'],'build.log')
clean=root/'clean';clean.mkdir()
archive=root/'candidate.tar'
subprocess.run(['git','archive','--format=tar','-o',str(archive),'HEAD'],cwd=repo,check=True)
with tarfile.open(archive) as stream:stream.extractall(clean,filter='data')
run([python,'-m','build','--no-isolation','--wheel','--outdir',root/'clean-dist',clean],'clean-build.log')
source=root/'sdist';source.mkdir()
with tarfile.open(next((root/'dist').glob('*.tar.gz'))) as stream:stream.extractall(source,filter='data')
run([python,'-m','build','--no-isolation','--wheel','--outdir',root/'sdist-dist',next(source.iterdir())],'sdist-build.log')
paths=[next((root/p).glob('*.whl')) for p in ['dist','clean-dist','sdist-dist']]
def members(p):
 with zipfile.ZipFile(p) as archive:return {n:hashlib.sha256(archive.read(n)).hexdigest() for n in archive.namelist() if n.startswith('peanalyzer/')}
values=[members(p) for p in paths]
assert values[0]==values[1]==values[2]
(root/'packaging.json').write_text(json.dumps({'candidate':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),'member_count':len(values[0]),'all_package_members_identical':True,'member_hashes':values[0],'archives':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}},indent=2)+'\n')
run([python,'-m','venv',root/'wheel-env'],'wheel-venv.log')
run([root/'wheel-env/bin/pip','install','-r',repo/'requirements-dev.lock','-r',repo/'requirements-gui.lock',paths[0]],'wheel-install.log')
wheel_tests=root/'wheel-tests-input';wheel_tests.mkdir()
with tarfile.open(archive) as stream:stream.extractall(wheel_tests,filter='data')
run([root/'wheel-env/bin/python','-c','import json,peanalyzer; from pathlib import Path; assert "site-packages" in peanalyzer.__file__; print(json.dumps({"version":peanalyzer.__version__,"import_path":peanalyzer.__file__}))'],'wheel-import.json',wheel_tests)
print('package members',len(values[0]),flush=True)
