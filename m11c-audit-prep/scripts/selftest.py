"""Baseline authority and independent-tool canaries; no candidate access."""
import argparse,copy,itertools,json,os,subprocess,tempfile
from pathlib import Path
from types import SimpleNamespace
from common import baseline_import,write,read,inventory,diff,sha
from force_oracle import graph,closure,from_plan,union_owned,FAMILIES
from recovery_identity import capture
from pure_guard import inspection

def run(checkout,output):
    baseline_import(checkout)
    from peanalyzer import workflow as w
    destination=Path(output);destination.mkdir(exist_ok=False,parents=True)
    counts=dict(valid_closures=0,invalid_analyze_closures=0);rows=[]
    for mode in ('run','analyze'):
        nodes=graph(mode,['bc001','bc002'],['T1','T2'])
        plan=SimpleNamespace(mode=mode,nodes=[SimpleNamespace(**n) for n in nodes])
        for bits in itertools.product((False,True),repeat=7):
            families=[f for f,b in zip(FAMILIES,bits) if b]
            if mode=='analyze' and 'demux' in families:
                for f in (lambda:closure(mode,['bc001','bc002'],['T1','T2'],families),lambda:w.force_closure(plan,families)):
                    try:f()
                    except (ValueError,w.WorkflowError):pass
                    else:raise AssertionError('Forbidden analyze demux force accepted')
                counts['invalid_analyze_closures']+=1;continue
            oracle=closure(mode,['bc001','bc002'],['T1','T2'],families,[n['stage_id'] for n in nodes])
            assert set(oracle['closure'])==w.force_closure(plan,families)
            assert set(oracle['closure']).isdisjoint(oracle['proven_reused'])
            assert set(oracle['closure'])|set(oracle['proven_reused'])=={n['stage_id'] for n in nodes}
            counts['valid_closures']+=1
            if len(families)==1:rows.append(dict(mode=mode,**oracle))
    write(destination/'force-closures.json',dict(counts=counts,single_families=rows))
    root=destination/'identity-workspace';(root/'workflow').mkdir(parents=True);source=destination/'source';source.write_bytes(b'original');backend=destination/'backend';backend.write_bytes(b'backend')
    plan=dict(mode='run',output=str(root),expected_samples=['bc001'],expected_targets=['T1'],nodes=graph('run',['bc001'],['T1']),inputs={'r1':dict(source_path=str(source),sha256=sha(source),snapshot=None)},normalized_options={})
    write(root/'workflow/plan.json',plan)
    software=dict(commit='frozen',dirty=False);runtime=dict(executable=str(backend),version='pinned')
    def token():return capture(root,software,runtime,['routing'])['identity_sha256']
    original=token();assert token()==original;mutations=[]
    def check(label,change,undo):
        before=token();change()
        try:assert token()!=before
        except ValueError:pass
        finally:undo()
        mutations.append(label)
    check('source_bytes',lambda:source.write_bytes(b'changed'),lambda:source.write_bytes(b'original'))
    result=root/'result.json';check('stage_inventory',lambda:result.write_text('{}'),lambda:result.unlink())
    marker=root/'workflow_manifest.json';check('completion_manifest',lambda:marker.write_text('{}'),lambda:marker.unlink())
    lock=root.with_name('.'+root.name+'.m7-lock');check('lock_appears',lambda:lock.touch(),lambda:lock.unlink())
    check('software',lambda:software.update(commit='changed'),lambda:software.update(commit='frozen'))
    check('backend_bytes',lambda:backend.write_bytes(b'changed'),lambda:backend.write_bytes(b'backend'))
    original_plan=(root/'workflow/plan.json').read_bytes();check('plan_bytes',lambda:(root/'workflow/plan.json').write_bytes(original_plan+b'\n'),lambda:(root/'workflow/plan.json').write_bytes(original_plan))
    # A path swap is not accepted as equivalent merely because file bytes match.
    moved=root.with_name('moved')
    def swap():root.rename(moved);root.symlink_to(moved,target_is_directory=True)
    def undo():root.unlink();moved.rename(root)
    check('workspace_symlink',swap,undo)
    different=capture(root,software,runtime,['metrics'])['identity_sha256'];assert different!=token();mutations.append('requested_force')
    negatives=[];alias=w.execute_workflow
    before=inventory(root)
    with inspection() as attempts:
        assert w.force_closure(SimpleNamespace(mode='run',nodes=[SimpleNamespace(**n) for n in plan['nodes']]),['routing'])
        assert read(root/'workflow/plan.json')==plan
    assert not attempts and inventory(root)==before
    actions=[('write',lambda:(root/'illegal').write_text('x')),('delete',lambda:source.unlink()),('subprocess',lambda:subprocess.run(['/bin/true'],check=True)),('preimported_execution_alias',lambda:alias()),('planning_version_probe',lambda:w.build_workflow_plan(mode='run',samples=None,targets=None,config=None,output=None,crispresso=None,runtime_digest=None))]
    for name,action in actions:
        try:
            with inspection():action()
        except AssertionError as exc:
            assert 'PURE_INSPECTION_VIOLATION' in str(exc);negatives.append(name)
        else:raise AssertionError('Missing tripwire: '+name)
    assert inventory(root)==before and source.read_bytes()==b'original'
    # A caller swallowing a rejected write still fails the guard at exit.
    try:
        with inspection():
            try:(root/'illegal').write_text('x')
            except AssertionError:pass
    except AssertionError:negatives.append('swallowed_violation')
    else:raise AssertionError('Swallowed violation escaped')
    write(destination/'selftest.json',dict(baseline=__import__('common').BASE,**counts,single_family_rows=len(rows),identity_mutations=mutations,purity_negative_canaries=negatives,pure_read_and_closure_pass=True,source_unchanged=True))
    return counts
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--baseline',required=True);p.add_argument('--output',required=True);a=p.parse_args();print(run(a.baseline,a.output))
