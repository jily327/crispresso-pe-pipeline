"""Each caught profiling violation gets a fresh guard (Python clears on error)."""
import json,subprocess,sys
from types import SimpleNamespace
from tripwires import Tripwire
from peanalyzer.workflow import execute_workflow as imported_alias,build_workflow_plan,force_closure

def run():
    outcomes={}
    for name,fn in [('captured_executor_alias',lambda:imported_alias()),('probing_plan',lambda:build_workflow_plan(mode="run",samples=None,targets=None,config=None,output=None,crispresso=None,runtime_digest=None)),
                    ('forbidden_force',lambda:force_closure(None,())),('subprocess',lambda:subprocess.run([sys.executable,'-c','raise SystemExit(91)']))]:
        guard=Tripwire()
        try:
            with guard.installed():fn()
        except AssertionError as exc:outcomes[name]=str(exc)
        else:raise AssertionError('tripwire failed: '+name)
        assert guard.calls
    plan=SimpleNamespace(mode='run',nodes=[])
    guard=Tripwire();guard.accepted('s','s','p','p')
    with guard.installed():assert force_closure(plan,())==set()
    outcomes['accepted_empty_force_bookkeeping']='allowed; no recovery selected'
    guard=Tripwire();guard.accepted('s','s','p','p')
    try:
        with guard.installed():force_closure(plan,('all',))
    except AssertionError as exc:outcomes['accepted_nonempty_force']=str(exc)
    else:raise AssertionError('force exposed')
    return outcomes
if __name__=='__main__':print(json.dumps(run(),indent=2))
