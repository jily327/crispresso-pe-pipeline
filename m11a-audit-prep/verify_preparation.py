from pathlib import Path
import hashlib,io,json,re,subprocess,tarfile
P=Path(__file__).resolve().parent
repo=Path('/workspace/crispresso-pe-pipeline')
def git(*args):return subprocess.check_output(['git','-C',str(repo),*args])
before=json.loads((P/'repository-before.json').read_text())
after={'local_heads':git('for-each-ref','--format=%(refname) %(objectname)','refs/heads').decode(),'checkout':git('symbolic-ref','HEAD').decode(),'status':git('status','--porcelain').decode()}
assert after==before,(before,after)
exports=[]
for sha,root,subdir in [('40bd8ad8844fd07ce8a138b5520f7f0ec948030f',P/'backend-snapshot',None),('05cfc68b62215a4c52862e09f081eab1c75ba39f',P/'design-snapshot','gui-design-refresh')]:
 args=['archive','--format=tar',sha]+([subdir] if subdir else [])
 with tarfile.open(fileobj=io.BytesIO(git(*args))) as archive:
  expected=set();count=0
  for member in archive.getmembers():
   if member.isfile():
    path=root/member.name
    assert path.is_file() and not path.is_symlink(),path
    assert path.read_bytes()==archive.extractfile(member).read(),path
    expected.add(member.name);count+=1
   elif member.issym():
    assert (root/member.name).is_symlink()
    assert (root/member.name).readlink().as_posix()==member.linkname
    expected.add(member.name)
  actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() or p.is_symlink()}
  assert actual==expected,actual^expected
 exports.append({'sha':sha,'root':root.name,'regular_files':count,'byte_identity':True,'unexpected_files':0})
primary=['M11A_BACKEND_CONTRACT_AUDIT.md','M11A_ADVERSARIAL_TEST_MATRIX.md','M11A_ORACLE_FIXTURES.md','M11A_FINAL_AUDIT_CHECKLIST.md']
for name in primary:
 content=(P/name).read_text()
 assert content.count('```')%2==0,name
 for target in re.findall(r'\]\(([^)]+)\)',content):
  if not target.startswith(('https://','http://','#')):assert (P/target.split('#')[0]).exists(),(name,target)
cases=json.loads((P/'case-inventory.json').read_text());assert len(cases)==128 and len({c['id'] for c in cases})==128
assert all(c['candidate_status']=='NOT RUN — no stable candidate' for c in cases)
obs=json.loads((P/'oracle-observations.json').read_text());assert obs['checks']==obs['matched']==85
assert all(r['matched'] for r in obs['observations']) and obs['scientific_executions']==obs['subprocess_calls']==0
assert len(json.loads((P/'oracle-fixtures.json').read_text())['PE_SNP']['wt_sequence'])==180
report={'local_repository_unchanged':after==before,'local_working_tree_clean':after['status']=='','exports':exports,'primary_documents':primary,'unique_prepared_cases':128,'baseline_checks_matched':85,'scientific_executions':0,'subprocess_calls_during_oracles':0,'candidate_tested':False}
(P/'preparation-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
