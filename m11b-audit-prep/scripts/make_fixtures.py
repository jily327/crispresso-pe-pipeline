"""Generate SYNTHETIC INPUTS ONLY from the pinned baseline's test designs.

Usage: PYTHONPATH=<baseline>/src python make_fixtures.py <baseline> <new-dir>
Never invokes workflow/metrics/routing execution or a backend executable.
"""
import argparse,csv,json,sys
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('baseline');p.add_argument('output');a=p.parse_args()
    baseline=Path(a.baseline).resolve();root=Path(a.output).resolve();root.mkdir(exist_ok=False)
    import peanalyzer,yaml
    assert Path(peanalyzer.__file__).resolve().is_relative_to(baseline/'src'),'wrong import origin'
    sys.path.insert(0,str(baseline/'tests'))
    import m7_fixtures,m8_fixtures
    from peanalyzer.gui.setup_models import DraftContent,PETargetDraft,NucleaseTargetDraft,DraftSample
    from peanalyzer.gui.setup_validation import target_values
    from peanalyzer.schemas import Config,Target
    from peanalyzer.nuclease.targets import NucleaseTarget
    from peanalyzer.validation import load_targets
    for mode,fn in [('pe',m7_fixtures.fixture),('nuclease',m8_fixtures.fixture)]:
        dest=root/mode;options=fn(dest)
        # Current M11A supports summarize only and no tolerance request UI.
        for name in ('contrasts.yaml','policies.json'):(dest/name).unlink(missing_ok=True)
        rows=list(csv.DictReader((dest/'samples.csv').open()))
        samples=[DraftSample(**{**r,'paired':r['paired']=='true'}) for r in rows]
        targets=[];typed=[]
        for t in load_targets(dest/'targets.csv'):
            if mode=='pe':
                d=PETargetDraft(**{k:('' if v is None else v) for k,v in t.model_dump().items() if k in PETargetDraft.model_fields})
                typed.append(Target.model_validate(target_values(d)))
            else:
                d=NucleaseTargetDraft(target_name=t.target_name,copy_name=t.copy_name,wt_sequence=t.wt_sequence,profile='tigr_tas_v1',tigr_target_sequence=t.tigr_target_sequence,tigr_window='W2')
                typed.append(NucleaseTarget.model_validate(target_values(d)))
            targets.append(d)
        m7_fixtures.write_csv(dest/'targets.csv',list(typed[0].model_dump()),[t.model_dump() for t in typed])
        (dest/'config.yaml').write_text(yaml.safe_dump(Config(schema_version=1,demux={'profile':'custom'}).model_dump()))
        draft=DraftContent(analysis_name='Independent '+mode+' oracle',analysis_mode=targets[0].analysis_mode,
            samples=samples,targets=targets,library_profile='custom',trim_r1='8',trim_r2='8',workspace_name='gui-'+mode)
        (dest/'draft-template.json').write_text(draft.model_dump_json(indent=2)+'\n')
        if mode=='nuclease':
            (dest/'truth.json').write_text(json.dumps({'pairs':80,'sample_pairs':[20]*4,'deletion_origin':[2,4,14,16],
                'window':typed[0].window,'scientific_identity':typed[0].scientific_identity},indent=2)+'\n')
        args={k:(str(v.name) if isinstance(v,Path) else v) for k,v in options.items() if k!='output'}
        args['output']='SET_NEW_DIRECT_OUTPUT_ABSOLUTE';args['crispresso']='SET_SERVER_QUALIFIED_CORE'
        (dest/'direct-arguments.json').write_text(json.dumps(args,indent=2)+'\n')
    print(json.dumps({'synthetic_input_fixtures':2,'scientific_executions':0,'output':str(root)}))
if __name__=='__main__':main()
