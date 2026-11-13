import os,sys,subprocess,time,json,uuid
from pathlib import Path
sys.path.insert(0,'tests')
from m7_fixtures import fixture
from peanalyzer.metrics.production import RUNTIME_DIGEST
import tempfile
base=Path(tempfile.mkdtemp(prefix='peanalyzer-legacy-repro-'))
options=fixture(base/'inputs',samples=1,copies=1,reads=100000)
import csv
row=next(csv.DictReader(options['targets'].open()))
env=dict(os.environ)
for k in ('DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'):env.pop(k,None)
docker=['docker','--host=unix:///var/run/docker.sock']
name='peanalyzer-legacy-repro-'+uuid.uuid4().hex
cid=subprocess.check_output(docker+['run','-d','--name',name,'--network','none','--user',f'{os.getuid()}:{os.getgid()}','--mount',f'type=bind,src={base},dst={base}','--entrypoint','/bin/sleep',RUNTIME_DIGEST,'infinity'],env=env,text=True).strip()
args=['CRISPResso','-r1',str(options['r1']),'-r2',str(options['r2']),'--amplicon_seq',row['wt_sequence'],'--prime_editing_pegRNA_spacer_seq',row['pegRNA_spacer'],'--prime_editing_pegRNA_extension_seq',row['pegRNA_extension'],'--prime_editing_override_prime_edited_ref_seq',row['prime_edited_sequence'],'--name','legacy_repro','--output_folder','output','--suppress_report','--suppress_plots','--keep_intermediate']
try:
 with (base/'backend.log').open('w') as log:
  p=subprocess.Popen(docker+['exec','--user',f'{os.getuid()}:{os.getgid()}','--workdir',str(base),name,*args],env=env,stdout=log,stderr=subprocess.STDOUT)
  deadline=time.monotonic()+90
  while not any(f.stat().st_size for f in base.glob('output/**/CRISPResso_RUNNING_LOG.txt')):
   assert p.poll() is None,'Core exited before nonempty barrier'
   assert time.monotonic()<deadline,'No backend output'
   time.sleep(.01)
  before=json.loads(subprocess.check_output(docker+['container','inspect',cid],env=env,text=True))[0]
  p.kill();p.wait();time.sleep(.2)
  top=subprocess.check_output(docker+['top',cid,'-eo','pid,comm,args'],env=env,text=True)
  alive=any('CRISPResso' in line and '--name legacy_repro' in line for line in top.splitlines())
  assert alive,top
  report={'image':before['Config']['Image'],'image_id':before['Image'],'local_cli_returncode':p.returncode,'genuine_nonempty_files':[str(f.relative_to(base)) for f in base.glob('output/**/*') if f.is_file() and f.stat().st_size],'core_alive_after_local_cli_sigkill':alive,'container_id':cid,'scope':'Dedicated synthetic persistent-container model; no user installation touched'}
  Path(os.environ.get('PEANALYZER_LEGACY_EVIDENCE','legacy-reproduction.json')).write_text(json.dumps(report,indent=2)+'\n')
finally:subprocess.run(docker+['rm','--force',cid],env=env,check=True,stdout=subprocess.DEVNULL)
