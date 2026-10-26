"""Strengthened post-run parity, frozen truth, lineage and force confirmation."""
import argparse
from pathlib import Path
from common import baseline_import,read,write,sha,inventory
from science_oracle import capture,compare
from force_oracle import from_plan

def run(checkout,runs,output,core):
    baseline_import(checkout)
    from peanalyzer import workflow as w
    from pure_guard import inspection
    runs=Path(runs);out=Path(output);out.mkdir(exist_ok=False,parents=True);evidence={}
    for mode,nums,den in [('pe',[4,8,16,20],24),('nuclease',[2,4,14,16],20)]:
        base=runs/mode;fresh=base/'fresh';recovered=base/'cancelled'
        w.verify_workflow_output(fresh);w.verify_workflow_output(recovered)
        original_comparison=compare(fresh,recovered);assert original_comparison['equal'],original_comparison
        projection=capture(fresh)
        for i,metric in enumerate(projection['metrics'].values()):
            values=metric['target_metrics'] if mode=='pe' else metric['metrics']
            for name in (['target_crispresso_native_pe','total_precise_pe'] if mode=='pe' else ['indel_fraction']):
                assert values[name]['numerator']==nums[i] and values[name]['denominator']==den
        # Warm authoritative verifier, then prove an allowed read-only verifier call.
        w.verify_workflow_output(fresh);before=inventory(fresh)
        with inspection() as attempts:assert w.verify_workflow_output(fresh).status=='COMPLETED'
        assert attempts==[] and inventory(fresh)==before
        options=read(base/'inputs/direct-arguments.json')
        for key in ('r1','r2','samples','targets','config'):options[key]=base/'inputs'/options[key]
        options.update(crispresso=core,contrasts=base/'inputs/contrasts.json',output=recovered)
        plan=read(recovered/'workflow/plan.json');expected=from_plan(plan,['routing'],[n['stage_id'] for n in plan['nodes']])
        forced=w.execute_workflow(resume=True,force=['routing'],**options)
        assert forced['executed_stages']==expected['closure'] and forced['reused_stages']==expected['proven_reused']
        w.verify_workflow_output(recovered);force_comparison=compare(fresh,recovered);assert force_comparison['equal'],force_comparison
        marker=sha(recovered/'workflow_manifest.json');resumed=w.resume_workflow(**options)
        assert resumed['executed_stages']==[] and sha(recovered/'workflow_manifest.json')==marker
        write(out/(mode+'-scientific-projection.json'),projection)
        evidence[mode]=dict(fresh_verifier='COMPLETED',recovery_verifier='COMPLETED',expected_numerators=nums,expected_denominator=den,full_projection_comparison=original_comparison,force_comparison=force_comparison,force_execution=forced,force_oracle=expected,completed_resume=resumed,read_only_authoritative_verifier_guard='PASS')
    write(out/'strengthened-science.json',evidence)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--baseline',required=True);p.add_argument('--runs',required=True);p.add_argument('--output',required=True);p.add_argument('--core',required=True);a=p.parse_args();run(a.baseline,a.runs,a.output,a.core);print('Full scientific provenance, child tables, 58 settings, truth and force/resume validated')
