"""Isolated-process inspection tripwires, paired with external filesystem/census checks."""
import contextlib,importlib,os,sys,threading
ACTIVE=None
INSTALLED=False
TARGETS={
 'peanalyzer.workflow':['build_workflow_plan','execute_workflow','resume_workflow','execute_stage','_invalidate','_snapshots'],
 'peanalyzer.demux':['demultiplex'],'peanalyzer.analysis_fastq':['prepare_analysis_fastqs'],
 'peanalyzer.routing':['route_analysis'],'peanalyzer.metrics.production':['run_metrics','collect_metrics'],
 'peanalyzer.nuclease.backend':['run_nuclease_metrics'],
 'peanalyzer.aggregation':['summarize','publish'],'peanalyzer.statistics':['stats','calculate_contrasts'],
 'peanalyzer.reporting':['generate_report','render_svg'],
 'peanalyzer.backend.pooled':['resolve_executable','run_pooled_diagnostic'],
 'peanalyzer.workflow_storage':['atomic_json']}

def audit(event,args):
    if ACTIVE is None:return
    bad=event in {'os.remove','os.rmdir','os.mkdir','os.rename','os.link','os.symlink','os.chmod','os.chown','os.utime','os.truncate','subprocess.Popen','os.system','os.fork','os.forkpty','os.posix_spawn','os.exec','shutil.rmtree','shutil.copyfile'}
    if event=='open':
        path,mode,flags=args
        bad=any(c in (mode or '') for c in 'wax+') or bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
    if bad:
        ACTIVE.append(dict(channel='audit',operation=event));raise AssertionError('PURE_INSPECTION_VIOLATION: '+event)

@contextlib.contextmanager
def inspection():
    global ACTIVE,INSTALLED
    codes={}
    for module,names in TARGETS.items():
        m=importlib.import_module(module)
        for name in names:
            f=getattr(m,name);codes[f.__code__]=module+'.'+name
    assert ACTIVE is None and sys.getprofile() is None and threading.getprofile() is None
    if not INSTALLED:sys.addaudithook(audit);INSTALLED=True
    attempts=[]
    def profile(frame,event,arg):
        if event=='call' and frame.f_code in codes:
            name=codes[frame.f_code];attempts.append(dict(channel='profile',operation=name));raise AssertionError('PURE_INSPECTION_VIOLATION: '+name)
    ACTIVE=attempts;sys.setprofile(profile)
    setter=getattr(threading,'setprofile_all_threads',threading.setprofile);setter(profile)
    try:yield attempts
    finally:
        sys.setprofile(None);setter(None);ACTIVE=None
    if attempts:raise AssertionError('Caught violations still fail inspection: '+str(attempts))
