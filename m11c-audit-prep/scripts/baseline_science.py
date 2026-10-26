"""Run only pinned baseline fresh/resume/force controls; never a future candidate."""
import argparse,copy,json,os,shutil,signal,sys
from pathlib import Path
from common import baseline_import,read,write,inventory,diff,digest,sha
from force_oracle import from_plan
from science_oracle import capture,compare

def run(checkout,fixtures,destination,core):
    baseline_import(checkout)
    from peanalyzer import workflow as w
    from peanalyzer.cli import sigterm_cleanup
    root=Path(destination).resolve();root.mkdir(exist_ok=False,parents=True)
    evidence=dict(baseline=__import__('common').BASE,import_origin=__import__('peanalyzer').__file__,software=w.software_identity().model_dump(),modes={})
    for mode in ('pe','nuclease'):
        inputs=root/mode/'inputs';shutil.copytree(Path(fixtures)/mode,inputs)
        options=read(inputs/'direct-arguments.json')
        for key in ('r1','r2','samples','targets','config'):options[key]=inputs/options[key]
        options.update(crispresso=core,contrasts=inputs/'contrasts.json')
        def args(name):return dict(options,output=root/mode/name)
        fresh=w.execute_workflow(**args('fresh'));w.verify_workflow_output(args('fresh')['output'])
        expected=capture(args('fresh')['output']);results={}
        for kind in ('failed','cancelled'):
            original=w.execute_stage
            def stop(plan,node,completed,argv):
                if node.stage_kind=='metrics':
                    if kind=='cancelled':os.kill(os.getpid(),signal.SIGTERM)
                    raise w.WorkflowError('AUDIT_INJECTED_FAILURE','Before first metrics stage',node.stage_id)
                return original(plan,node,completed,argv)
            w.execute_stage=stop
            try:
                with sigterm_cleanup():w.execute_workflow(**args(kind))
            except (w.WorkflowError,SystemExit) as exc:
                stopped=dict(error=type(exc).__name__,code=getattr(exc,'code',None))
            else:raise AssertionError('Controlled interruption did not occur')
            finally:w.execute_stage=original
            output=args(kind)['output'];assert not (output/'workflow_manifest.json').exists()
            assert not output.with_name('.'+output.name+'.m7-lock').exists()
            resumed=w.resume_workflow(**args(kind));assert w.verify_workflow_output(output).status=='COMPLETED'
            comparison=compare(args('fresh')['output'],output);assert comparison['equal'],comparison
            results[kind]=dict(interruption=stopped,resume=resumed,comparison=comparison)
        output=args('failed')['output'];plan=read(output/'workflow/plan.json')
        oracle=from_plan(plan,['routing'],[n['stage_id'] for n in plan['nodes']])
        forced=w.execute_workflow(resume=True,force=['routing'],**args('failed'))
        assert forced['executed_stages']==oracle['closure'] and forced['reused_stages']==oracle['proven_reused']
        assert w.verify_workflow_output(output).status=='COMPLETED'
        forced_comparison=compare(args('fresh')['output'],output);assert forced_comparison['equal'],forced_comparison
        # A completed resume must execute zero stages and preserve the completion marker bytes.
        before=(output/'workflow_manifest.json').read_bytes();nothing=w.resume_workflow(**args('failed'))
        assert nothing['executed_stages']==[] and (output/'workflow_manifest.json').read_bytes()==before
        evidence['modes'][mode]=dict(fresh=fresh,truth=read(inputs/'truth.json'),
            science_sha256=digest(expected),recovery=results,force_oracle=oracle,force_execution=forced,
            force_comparison=forced_comparison,completed_resume=nothing,
            metrics={k:(v.get('target_metrics') or v.get('metrics')) for k,v in expected['metrics'].items()},
            input_hashes=expected['input_hashes'])
        # Negative control: current baseline force deletes downstream before checking
        # the stale, unforced demux stage. Mutate only this disposable fixture copy.
        original_bytes=options['samples'].read_bytes()
        options['samples'].write_bytes(original_bytes.replace(b'bio1',b'bioX'))
        before=inventory(output)
        try:
            w.execute_workflow(resume=True,force=['routing'],**args('failed'))
        except w.WorkflowError as exc:error=dict(code=exc.code,stage=exc.stage_id,message=str(exc))
        else:raise AssertionError('Stale upstream unexpectedly accepted')
        finally:options['samples'].write_bytes(original_bytes)
        changed=diff(before,inventory(output));removed=[p for p,v in changed.items() if v['after'] is None]
        assert error['code']=='STALE_STAGE_IDENTITY' and removed
        evidence['modes'][mode]['baseline_partial_force_negative_control']=dict(error=error,
            downstream_paths_deleted=removed,changes=changed,expected_M11C='Reject before any scientific workspace mutation or invalidation')
    write(root/'science-evidence.json',evidence)
    return evidence

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--baseline',required=True);p.add_argument('--fixtures',required=True);p.add_argument('--output',required=True);p.add_argument('--core',required=True);a=p.parse_args()
    e=run(a.baseline,a.fixtures,a.output,a.core);print(json.dumps(dict(modes=list(e['modes']),fresh_resume_force_equal=True,partial_force_hazard_reproduced=True)))
