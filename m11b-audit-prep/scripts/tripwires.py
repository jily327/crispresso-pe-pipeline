"""Test-only in-process execution tripwires. Install in EVERY worker process.

Imports and capability bootstrap precede installation. No candidate Run endpoint
may toggle this guard: only the independent test controls the acceptance gate.
Use OS process tracing as well; Python hooks cannot police native/remote workers.
"""
import contextlib, importlib, sys, threading
from collections import Counter
EXECUTORS={
 'peanalyzer.workflow':('execute_workflow','execute_stage'),
 'peanalyzer.demux':('demultiplex',),
 'peanalyzer.analysis_fastq':('prepare_analysis_fastqs',),
 'peanalyzer.routing':('route_analysis',),
 'peanalyzer.metrics.production':('run_metrics',),
 'peanalyzer.backend.core':('run_confident_core',),
 'peanalyzer.backend.comparator':('run_comparator',),
 'peanalyzer.nuclease.backend':('run_nuclease_metrics',),
 'peanalyzer.aggregation':('summarize','collect_observations','summarize_groups'),
 'peanalyzer.statistics':('stats','calculate_contrasts','exact_unpaired','exact_paired','benjamini_hochberg'),
 'peanalyzer.reporting':('generate_report','render_svg'),
}
FORBIDDEN={'peanalyzer.workflow':('resume_workflow','_invalidate'),
 'peanalyzer.backend.pooled':('run_pooled_diagnostic',)}

class Tripwire:
    def __init__(self):
        self.phase='REVIEW';self.active=False;self.calls=Counter();self.codes={};self.old=None;self.thread_old=None
        for category,mapping in [('execute',EXECUTORS),('never',FORBIDDEN)]:
            for mod,names in mapping.items():
                module=importlib.import_module(mod)
                for name in names:
                    fn=getattr(module,name)
                    self.codes[fn.__code__]=(category,mod+'.'+name)
        # This captures imported aliases by function code, unlike patching one name.
        self.route_code=importlib.import_module('peanalyzer.routing').route_pair.__code__
        self.plan_code=importlib.import_module('peanalyzer.workflow').build_workflow_plan.__code__
        self.force_code=importlib.import_module('peanalyzer.workflow').force_closure.__code__
        sys.addaudithook(self.audit)
    def profile(self,frame,event,arg):
        if not self.active or event!='call':return
        item=self.codes.get(frame.f_code)
        if frame.f_code==self.force_code:
            self.calls['force_closure_bookkeeping']+=1
            if self.phase!='RUN' or frame.f_locals.get('families'):raise AssertionError('AUDIT_FORBIDDEN_FORCE')
        if frame.f_code in (self.route_code,self.plan_code) and self.phase=='REVIEW':
            item=('execute','route_pair_or_backend_probing_plan')
        if item:
            category,name=item;self.calls[name]+=1
            if category=='never' or self.phase!='RUN':raise AssertionError('AUDIT_EXECUTION_TRIPWIRE: '+name)
        if frame.f_code in self.codes and frame.f_code.co_name=='execute_workflow':
            if frame.f_locals.get('resume') or frame.f_locals.get('force'):raise AssertionError('AUDIT_FORBIDDEN_RECOVERY')
    def audit(self,event,args):
        if self.active and event in {'subprocess.Popen','os.system','os.posix_spawn','os.fork','os.forkpty'}:
            self.calls['process:'+event]+=1
            if self.phase!='RUN':raise AssertionError('AUDIT_PROCESS_BEFORE_RUN: '+event)
    @contextlib.contextmanager
    def installed(self):
        if sys.getprofile() or threading.getprofile():raise RuntimeError('use isolated test process without an existing profiler')
        self.active=True;sys.setprofile(self.profile);threading.setprofile(self.profile)
        try:yield self
        finally:
            self.active=False;sys.setprofile(None);threading.setprofile(None)
    def accepted(self,review_science,job_science,review_plan,job_plan):
        if review_science!=job_science or review_plan!=job_plan or not review_science or not review_plan:raise AssertionError('identity mismatch')
        self.phase='RUN'
    def verifying(self):self.phase='VERIFY'
