"""Candidate audit instrumentation, NOT application code.

Bind candidate imports before entering this context. Run isolated setup requests
under it; do not concurrently open legacy M10 workspaces (their authoritative
read verifier has a different, already-qualified validation boundary).
"""
from contextlib import contextmanager,ExitStack
import importlib,sys,threading
from unittest.mock import patch

FORBIDDEN={
 'peanalyzer.workflow':['build_workflow_plan','execute_workflow','resume_workflow','execute_stage','resolve_executable','force_closure','_invalidate','_snapshots','_manifest_csv'],
 'peanalyzer.demux':['demultiplex'],
 'peanalyzer.barcodes':['identify_barcode'],
 'peanalyzer.analysis_fastq':['prepare_analysis_fastqs'],
 'peanalyzer.routing':['route_pair','route_analysis','copy_placements','decide'],
 'peanalyzer.backend.pooled':['resolve_executable','run_pooled_diagnostic','write_amplicons'],
 'peanalyzer.backend.core':['run_confident_core'],
 'peanalyzer.backend.comparator':['run_comparator'],
 'peanalyzer.metrics.production':['run_metrics','collect_metrics'],
 'peanalyzer.metrics.family':['prepared_evidence','aligned_evidence','aggregate_family','reaggregate'],
 'peanalyzer.metrics.products':['prepared_products','aligned_products'],
 'peanalyzer.nuclease.backend':['run_nuclease_metrics'],
 'peanalyzer.aggregation':['collect_observations','summarize_groups','summarize','publish'],
 'peanalyzer.statistics':['stats','calculate_contrasts','exact_unpaired','exact_paired','benjamini_hochberg'],
 'peanalyzer.reporting':['generate_report','render_svg'],
}

@contextmanager
def zero_execution():
    """Record attempts even when application exception handlers swallow the trap.

    Function-code tracing also catches aliases/default arguments captured before
    monkeypatching. Python 3.12's all-thread hook covers preexisting worker pools.
    Run in a dedicated audit process: replacing another profiler is not supported.
    This does not instrument arbitrary native extensions or external server
    processes; install it INSIDE the candidate API process for HTTP/browser runs.
    """
    originals=[]
    for module,names in FORBIDDEN.items():
        mod=importlib.import_module(module)
        for name in names:
            if not hasattr(mod,name):raise AssertionError(f'Trap symbol changed: {module}.{name}; review, do not silently omit')
            originals.append((mod,name,getattr(mod,name)))
    attempts=[]
    codes={fn.__code__:module.__name__+'.'+name for module,name,fn in originals if hasattr(fn,'__code__')}
    assert sys.getprofile() is None and threading.getprofile() is None,'Use an isolated, unprofiled audit process'
    def deny(name):
        def fail(*a,**kw):
            attempts.append(name);raise AssertionError('M11A_ZERO_EXECUTION: '+name)
        return fail
    def profile(frame,event,arg):
        if event=='call' and frame.f_code in codes:
            name=codes[frame.f_code];attempts.append(name);raise AssertionError('M11A_ZERO_EXECUTION: '+name)
    with ExitStack() as stack:
        for module,name,fn in originals:stack.enter_context(patch.object(module,name,deny(module.__name__+'.'+name)))
        # Bound module aliases are common; profile hook handles captures not found here.
        lookup={id(fn):module.__name__+'.'+name for module,name,fn in originals}
        for name,module in list(sys.modules.items()):
            if name.startswith('peanalyzer.') and module:
                for key,value in list(vars(module).items()):
                    if id(value) in lookup:stack.enter_context(patch.object(module,key,deny(lookup[id(value)])))
        for name in ['Popen','run','check_output','check_call','call']:
            stack.enter_context(patch('subprocess.'+name,deny('subprocess.'+name)))
        for name in ['system','popen','fork','forkpty','posix_spawn','posix_spawnp','execv','execve','execvp','execvpe']:
            import os
            if hasattr(os,name):stack.enter_context(patch.object(os,name,deny('os.'+name)))
        for name in ['create_subprocess_exec','create_subprocess_shell']:
            stack.enter_context(patch('asyncio.'+name,deny('asyncio.'+name)))
        sys.setprofile(profile)
        if hasattr(threading,'setprofile_all_threads'):threading.setprofile_all_threads(profile)
        else:threading.setprofile(profile)
        try:yield attempts
        finally:
            sys.setprofile(None)
            if hasattr(threading,'setprofile_all_threads'):threading.setprofile_all_threads(None)
            else:threading.setprofile(None)
    if attempts:raise AssertionError('M11A forbidden attempts: '+repr(attempts))
