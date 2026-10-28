"""Maintainer-only synthetic installed-application smoke; no production hooks.
Use --root NEW_DIRECTORY. Starts only the official launcher via the wrappers.
"""
import argparse,hashlib,json,os,re,selectors,shutil,subprocess,sys,time,urllib.request
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--root',type=Path,required=True);p.add_argument('--core',type=Path,required=True);a=p.parse_args()
a.package=a.package.absolute();a.root=a.root.absolute();a.core=a.core.absolute()
a.root.mkdir(parents=True,exist_ok=False);(a.root/'analyses').mkdir()
shutil.copytree(a.package/'fixtures',a.root/'inputs')
def inventory(paths):
    return {str(p):(p.stat().st_size,p.stat().st_mtime_ns,hashlib.sha256(p.read_bytes()).hexdigest()) for root in paths for p in root.rglob('*') if p.is_file()}
def request(base,token,path,body=None,method=None):
    req=urllib.request.Request(base+path,data=None if body is None else json.dumps(body).encode(),headers={'X-Viewer-Token':token,'Content-Type':'application/json','Origin':base},method=method)
    with urllib.request.urlopen(req,timeout=120) as response:return json.load(response)
def launch(args):
    command=list(map(str,args));command=(['/bin/bash']+command) if command[0].endswith('.sh') else command
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    deadline=time.monotonic()+30;selector=selectors.DefaultSelector();selector.register(process.stdout,selectors.EVENT_READ)
    while time.monotonic()<deadline:
        if process.poll() is not None:raise AssertionError('Launcher exited before URL')
        if selector.select(.2):
            line=process.stdout.readline()
            match=re.search(r'Open (http://127\.0\.0\.1:(\d+))/#(\S+)',line)
            if match:
                selector.close();base,port,token=match.groups()
                while True:
                    try:request(base,token,'/api/v1/capabilities');break
                    except OSError:
                        if time.monotonic()>deadline:raise
                        time.sleep(.1)
                # Linux TCP table: the listener must be loopback, not 0.0.0.0.
                entries=[r.split()[1] for r in Path('/proc/net/tcp').read_text().splitlines()[1:] if r.split()[3]=='0A' and int(r.split()[1].split(':')[1],16)==int(port)]
                assert entries==[f'0100007F:{int(port):04X}'],entries
                return process,base,token
    process.terminate();process.wait();raise TimeoutError('Launcher URL not printed')
def stop(process):
    if process.poll() is None:process.terminate()
    process.wait(timeout=30);process.stdout.close()
summary={'node_available':shutil.which('node'),'installed_python':sys.executable,'modes':{}}
from importlib.metadata import version
import peanalyzer
assert 'site-packages' in peanalyzer.__file__
summary.update(package_version=version('crispresso-pe-pipeline'),import_origin=peanalyzer.__file__)
# Doctor touches no scientific input/output files. Do not inspect recovery keys.
before=inventory([a.root/'inputs',a.root/'analyses',a.core.parent.parent/'cache'])
doc=subprocess.run(['/bin/bash',str(a.package/'doctor.sh'),'--core',str(a.core),'--output-root',str(a.root/'analyses'),'--input',str(a.root/'inputs/pe/raw_R1.fastq.gz'),'--input',str(a.root/'inputs/pe/raw_R2.fastq.gz')],capture_output=True,text=True)
assert doc.returncode==0,doc.stdout+doc.stderr
summary['doctor']=json.loads(doc.stdout);assert before==inventory([a.root/'inputs',a.root/'analyses',a.core.parent.parent/'cache'])
summary['doctor_input_output_cache_unchanged']=True
# Official view-only launcher: no output creation, and bundled assets are present.
proc,base,token=launch(['peanalyzer-viewer','--view-only'])
try:
    with urllib.request.urlopen(base) as r:page=r.read().decode()
    assets=re.findall(r'(?:src|href)="([^"]+\.(?:js|css))"',page);assert assets
    for asset in assets:
        with urllib.request.urlopen(base+asset) as r:assert r.status==200 and r.read()
    summary['loopback_view_only']={'url_has_token_fragment':True,'bind':'127.0.0.1','bundled_assets':assets,'run_available':request(base,token,'/api/v1/setup/capabilities')['run_available']}
    assert not summary['loopback_view_only']['run_available']
finally:stop(proc)
for mode in ('pe','nuclease'):
    inputs=a.root/'inputs'/mode;parent=a.root/'analyses';workspace=parent/('smoke-'+mode)
    proc,base,token=launch([a.package/'launch-new-analysis.sh',inputs/'raw_R1.fastq.gz',inputs/'raw_R2.fastq.gz',parent,a.core])
    try:
        caps=request(base,token,'/api/v1/setup/capabilities');files=caps['files']
        def ref(label):return next(f['file_id'] for f in files if f['label']==label)
        content=json.loads((inputs/'draft-values.json').read_text());content.update(r1=ref('raw_R1.fastq.gz'),r2=ref('raw_R2.fastq.gz'),output_root=next(f['file_id'] for f in files if f['kind']=='output_root'))
        draft=request(base,token,'/api/v1/drafts',{})
        draft=request(base,token,'/api/v1/drafts/'+draft['draft_id'],{'revision':0,'content':content},'PATCH')
        validation=request(base,token,'/api/v1/drafts/'+draft['draft_id']+'/validate',{'revision':draft['revision']});assert validation['status']=='VALID',validation
        preview=request(base,token,f"/api/v1/drafts/{draft['draft_id']}/preview?revision={draft['revision']}")
        assert not workspace.exists(),'Setup wrote a scientific workspace'
        job=request(base,token,'/api/v1/jobs',{k:v for k,v in dict(draft_id=draft['draft_id'],revision=draft['revision'],plan_identity_sha256=preview['plan_identity_sha256'],scientific_identity_sha256=preview['scientific_identity_sha256']).items()})
        deadline=time.monotonic()+240
        while job['state'] not in ('COMPLETED','FAILED','CANCELLED'):
            assert time.monotonic()<deadline,job
            time.sleep(.2);job=request(base,token,'/api/v1/jobs/'+job['job_id'])
        assert job['state']=='COMPLETED',job
        view=request(base,token,'/api/v1/workspaces/'+job['workspace_id']);assert view['mode']==content['analysis_mode']
        from peanalyzer.workflow import verify_workflow_output
        assert verify_workflow_output(workspace).status=='COMPLETED'
        metric=json.loads((workspace/'metrics/bc001/T1/result.json').read_text())
        value=metric['target_metrics']['total_precise_pe'] if mode=='pe' else metric['metrics']['indel_fraction']
        expected=(2,24) if mode=='pe' else (8,20);assert (value['numerator'],value['denominator'])==expected
        summary['modes'][mode]={'state':job['state'],'metric':{'numerator':value['numerator'],'denominator':value['denominator']},'open_results_verified':True,'setup_wrote_workspace':False}
    finally:stop(proc)
    # Reopen via the official read-only wrapper; existing M10 performs verification.
    before=inventory([workspace,inputs])
    proc,base,token=launch([a.package/'launch-view-results.sh',workspace])
    try:
        registration=request(base,token,'/api/v1/workspaces')[0]
        opened=request(base,token,'/api/v1/workspaces/open',{'registration_id':registration['registration_id']})
        assert opened['mode']==content['analysis_mode'];assert before==inventory([workspace,inputs])
        summary['modes'][mode]['view_wrapper_unchanged']=True
    finally:stop(proc)
    proc,base,token=launch([a.package/'launch-recovery.sh',workspace,a.core])
    try:
        registration=request(base,token,'/api/v1/recovery/workspaces')[0]
        inspected=request(base,token,'/api/v1/recovery',{'registration_id':registration['registration_id']})
        assert inspected['classification']=='COMPLETED' and not inspected['executable'],inspected
        assert before==inventory([workspace,inputs]);summary['modes'][mode]['recovery_wrapper_completed_readonly']=True
    finally:stop(proc)
(a.root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
