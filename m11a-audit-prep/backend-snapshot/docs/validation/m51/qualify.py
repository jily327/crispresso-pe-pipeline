"""Portable M5.1 probes: synthetic JSON only, no backend or prior checkout."""
import argparse
import json
from pathlib import Path
import random
import subprocess
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO/'tests'))
from peanalyzer import __version__
from peanalyzer.aggregation import AggregationError
from m5_fixtures import dataset,change_record,read_samples,write_samples,write_json,write_manifest
from test_m51 import entries,remove_results,invoke,scientific,scientific_sha,diagnostic


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--fixtures',type=Path,required=True,help='Reusable deterministic fixture root; use the same path for byte parity')
    args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=False)
    before=json.loads(Path(__file__).with_name('before.json').read_text())
    report=dict(version=__version__,complete={},partial={},controls={},cli={})
    assert __version__=='0.5.1'
    for paired in (False,True):
        inputs=dataset(args.fixtures/('paired' if paired else 'unpaired'),paired=paired)
        for command in ('summarize','stats'):
            name=('paired' if paired else 'unpaired')+'_'+command
            result=invoke(command,inputs,output=out/name)
            assert scientific_sha(result)==before['complete'][name]['scientific_sha256']
            report['complete'][name]=dict(scientific_sha256=scientific_sha(result),parent_scientific_equal=True,
                observations=len(result.observations),summaries=len(result.group_summaries),
                contrasts=[c.model_dump(mode='json') for c in result.contrasts])
            paths=entries(inputs);random.Random(51).shuffle(paths);write_manifest(inputs['manifest_path'],paths)
            assert scientific(invoke(command,inputs))==scientific(result)
            report['complete'][name]['manifest_order_invariant']=True
            # Restore the common fixture bytes for the next command/replay.
            write_manifest(inputs['manifest_path'],sorted(paths))
    attacks=[('A003-T2',('T1','T2'),{'A003-T2.json'},{'barcode-A003':['T2']}),
             ('B002-T1',('T1','T2'),{'B002-T1.json'},{'barcode-B002':['T1']}),
             ('multiple_missing',('T3','T1','T2'),{'A003-T2.json','A003-T3.json'},{'barcode-A003':['T2','T3']})]
    for name,targets,removed,missing in attacks:
        inputs=dataset(args.fixtures/name,targets=targets);remove_results(inputs,removed)
        for command in ('summarize','stats'):
            messages=[]
            for order in ('original','shuffled'):
                if order=='shuffled':
                    paths=entries(inputs);random.Random(51).shuffle(paths);write_manifest(inputs['manifest_path'],paths)
                output=out/(name+'-'+command+'-'+order)
                try:invoke(command,inputs,output=output)
                except AggregationError as error:messages.append(str(error))
                else:raise AssertionError('partial collection succeeded')
                assert messages[-1]==diagnostic(missing)
                assert not output.exists() and not list(out.glob('.'+output.name+'*'))
            report['partial'][name+'_'+command]=dict(error=messages[0],manifest_order_invariant=messages[0]==messages[1],completed_output=False)
        if name=='A003-T2':
            for command in ('summarize','stats'):
                output=out/('cli-'+command)
                argv=[str(Path(sys.executable).parent/'peanalyzer'),command,'--manifest',str(inputs['manifest_path']),
                      '--samples',str(inputs['samples_path']),'--output',str(output)]
                if command=='stats':argv+=['--contrasts',str(inputs['contrasts_path'])]
                result=subprocess.run(argv,capture_output=True,text=True)
                assert result.returncode==2 and diagnostic(missing) in result.stderr
                assert not output.exists() and not list(out.glob('.'+output.name+'*'))
                report['cli'][command]=dict(exit_code=2,stderr=result.stderr.strip(),completed_output=False,publication_leftovers=False)
    for owner in ('A001','B003'):
        inputs=dataset(args.fixtures/('unique-'+owner))
        remove_results(inputs,{p for p in entries(inputs) if p.endswith('-T2.json') and not p.startswith(owner+'-')})
        missing={'barcode-'+s:['T2'] for s in ('A001','A002','A003','B001','B002','B003') if s!=owner}
        try:invoke('summarize',inputs)
        except AggregationError as error:
            assert str(error)==diagnostic(missing)
            report['partial']['unique_'+owner]=dict(error=str(error))
        else:raise AssertionError('unique target silently accepted')
    for kind in ('added_unused','remove_all_A003','missing_policy','BLOCKED','NOT_ASSESSABLE'):
        inputs=dataset(args.fixtures/kind)
        if kind=='added_unused':
            rows=read_samples(inputs['samples_path']);rows.append(rows[0]|dict(sample_name='unused',barcode_id='barcode-unused',biological_replicate='unused'))
            write_samples(inputs['samples_path'],rows)
        elif kind=='remove_all_A003':remove_results(inputs,{'A003-T1.json','A003-T2.json'})
        elif kind=='missing_policy':
            path=inputs['manifest_path'].parent/'A003-T2.json';raw=json.loads(path.read_text())
            raw['derived_metrics']['target'].pop('policy1');write_json(path,raw)
        else:change_record(inputs['manifest_path'].parent/'A003-T2.json',kind)
        report['controls'][kind]={}
        for command in ('summarize','stats'):
            result=invoke(command,inputs)
            groups=[g.model_dump(mode='json') for g in result.group_summaries if g.target_name=='T2' and g.condition.treatment=='A'
                    and (g.metric_name=='target_crispresso_native_pe' or g.metric_name=='total_pe_family' and g.policy_id=='policy1')]
            if kind in ('added_unused','remove_all_A003'):
                assert result.unused_metadata_sample_ids==(['unused'] if kind=='added_unused' else ['A003'])
                assert len(result.observations)==(144 if kind=='added_unused' else 120)
            elif kind=='missing_policy':
                assert len(result.observations)==143
                g=next(g for g in groups if g['policy_id']=='policy1')
                row=next(s for s in g['sample_assessments'] if s['sample_name']=='A003')
                assert row['status']=='MISSING_METRIC' and row['reason_codes']==['METRIC_NOT_PRESENT']
            else:
                row=next(r for r in result.observations if r.sample_id=='barcode-A003' and r.target_name=='T2' and r.metric_name=='target_crispresso_native_pe')
                assert row.status==kind and row.numerator is row.denominator is row.fraction is None
            report['controls'][kind][command]=dict(collection_succeeded=True,observations=len(result.observations),
                unused_metadata_sample_ids=result.unused_metadata_sample_ids,groups=groups)
    (out/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print('PASS: coverage attacks, controls, CLI failures, parent parity and manifest ordering')


if __name__=='__main__':main()
