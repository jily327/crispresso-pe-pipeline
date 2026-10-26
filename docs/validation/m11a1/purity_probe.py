"""Run in source or installed-wheel environment; fixtures precede audit guards."""
import copy,csv,gzip,json,os,sys
from pathlib import Path
from m7_fixtures import fixture
from m11a1_guards import zero_execution
from test_m11a1 import ambiguous_deletion, replicate_rows
from peanalyzer.gui.drafts import DraftStore,SetupReferences
from peanalyzer.gui.setup_models import DraftContent,DraftPatch,PETargetDraft
from gui_helpers import fingerprint
import peanalyzer

root=Path(sys.argv[1]);options=fixture(root/'inputs',samples=2,copies=2)
output=root/'output-proposals';output.mkdir()
empty=[root/f'empty_R{i}.fastq.gz' for i in (1,2)]
for p in empty:p.write_bytes(gzip.compress(b'',mtime=0))
protected=Path('/workspace/validation/m101/source-tests/m10/precise_edit/workflow')
refs=SetupReferences([options['r1'],options['r2'],*empty],output_roots=[output])
ids=list(refs.entries)
samples=list(csv.DictReader(options['samples'].open()))
for sample in samples:sample['paired']=False
rows=[{k:v for k,v in r.items() if k in PETargetDraft.model_fields} for r in csv.DictReader(options['targets'].open())]
data=DraftContent(analysis_name='Purity probe',r1=ids[0],r2=ids[1],samples=samples,targets=rows,analysis_mode='precise_edit',library_profile='custom',trim_r1='8',trim_r2='8',output_root=ids[-1],workspace_name='never-created').model_dump()
cases={'valid':data}
x=copy.deepcopy(data);x['samples']=replicate_rows(x['samples'],'duplicate');cases['duplicate']=x
x=copy.deepcopy(data);x['targets']=ambiguous_deletion();cases['ambiguous']=x
x=copy.deepcopy(data);x['r1'],x['r2']=ids[2:4];cases['empty']=x
x=copy.deepcopy(data);x['samples'][0]['paired']=True;cases['block']=x

def inventory():
 return {str(p.relative_to(root)):(p.read_bytes(),p.stat().st_mtime_ns) if p.is_file() else 'directory' for p in root.rglob('*')}
before=inventory();workspace_before=fingerprint(protected);writes=[];enabled=False
mutations={'os.mkdir','os.remove','os.rmdir','os.rename','os.link','os.symlink','os.truncate','os.chmod','os.chown','os.utime'}
def audit(event,args):
 if not enabled:return
 write=event in mutations
 if event=='open':
  _,mode,flags=args
  write=bool(isinstance(mode,str) and any(x in mode for x in 'wax+')) or bool(isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
 if write:
  writes.append(event);raise AssertionError('SETUP_WRITE_ATTEMPT: '+event)
sys.addaudithook(audit)
store=DraftStore(refs,protected=[protected]);observed={}
with zero_execution() as attempts:
 enabled=True
 try:
  for name,values in cases.items():
   d=store.create();d=store.patch(d.draft_id,DraftPatch(revision=0,content=DraftContent.model_validate(values)))
   r=store.validate(d.draft_id,d.revision)
   if r.status=='VALID':assert store.preview(d.draft_id,d.revision)==r.preview
   observed[name]={'status':r.status,'issues':[i.model_dump() for i in r.issues]}
 finally:enabled=False
assert {k:v['status'] for k,v in observed.items()}==dict(valid='VALID',duplicate='INVALID',ambiguous='VALID',empty='INVALID',block='INVALID')
assert not writes and not attempts and inventory()==before and fingerprint(protected)==workspace_before
record={'import_origin':peanalyzer.__file__,'cases':observed,'guarded_executor_attempts':len(attempts),'filesystem_write_attempts':len(writes),'input_output_bytes_and_mtimes_unchanged':True,'existing_workspace_and_sources_unchanged':True,'proposed_output_absent':not(output/'never-created').exists()}
Path(str(root)+'-evidence.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k!='cases'}))
