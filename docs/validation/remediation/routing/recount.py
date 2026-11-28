"""Recount preserved managed and independent native runs using the installed integrated wheel."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path

import peanalyzer
from peanalyzer.analysis_verify import verify_analysis_output
from peanalyzer.backend.core import verify_routing_output
from peanalyzer.backend.native_artifacts import extract_native
from peanalyzer.demux_verify import sha256_file
from peanalyzer.fastq import paired_fastq, read_id
from peanalyzer.metrics.production import collect_metrics, RUNTIME_DIGEST
from peanalyzer.observability import assess_pair
from peanalyzer.schemas import Target


def read(p): return json.loads(p.read_bytes())


def recount(base, package, output):
    assert (package/'READY').is_file()
    assert Path(peanalyzer.__file__).resolve().is_relative_to((package/'env').resolve())
    modules=['backend/core','backend/metrics','backend/insertion_products','backend/extension_alleles','backend/comparator',
             'backend/native_artifacts','routing','routing_eligibility','geometry','observability','metrics/production']
    source_hashes={}
    for m in modules:
        src=package/'source/src/peanalyzer'/(m+'.py')
        installed=Path(peanalyzer.__file__).parent/(m+'.py')
        source_hashes[m]=sha256_file(src)
        assert source_hashes[m]==sha256_file(installed)
    cells=[('f01',base/'f01-native',base/'after/prepared',base/'after/routing'),
           ('alsp-forward',base/'alsp01/metrics',base/'alsp01/prepared',base/'alsp01/routing'),
           ('alsp-reverse',base/'alsp01/reverse_metrics',base/'alsp01/prepared',base/'alsp01/reverse_routing'),
           ('hibit',base/'hibit03/metrics',base/'hibit03/prepared',None)]
    summary={};evidence={}
    for key,cell,prep,route in cells:
        doc=read(cell/'native_runs.json')
        if route:
            routing=verify_routing_output(route)
            targets=[Target.model_validate(t) for t in routing['targets']]
        else:
            targets=[Target.model_validate(t) for t in doc['runs'][0]['original_reference']]
        r=collect_metrics(analysis_root=prep,sample_id='1B',targets=targets,analysis_id=key,
                          comparator_root=cell/'comparator',routing_root=route,
                          copy_roots={t.copy_name:cell/'copies'/t.copy_name for t in targets},runtime_digest=RUNTIME_DIGEST)
        runs=[]
        for run in doc['runs']:
            if run['execution_status']!='COMPLETED':
                assert run['id']=='comparator/copy2' and key.startswith('alsp')
                continue
            managed=cell/run['paths']['info']
            repeat=base/'direct'/(key+'-'+run['id'].replace('/','-'))
            direct,=(repeat/'replay').rglob('CRISPResso2_info.json')
            parity=read(repeat/'parity.json')
            assert parity['status']=='PASS' and not parity['differing_parameters'] and not parity['allele_differences']
            assert all(v['difference']==0 for v in parity['integers'])
            assert sha256_file(managed)==parity['managed_info_sha256'] and sha256_file(direct)==parity['direct_info_sha256']
            assert sha256_file(cell/run['paths']['r1'])==parity['input_sha256'][0]
            assert sha256_file(cell/run['paths']['r2'])==parity['input_sha256'][1]
            count=extract_native(managed)
            repeated=extract_native(direct)
            # Physical output directories differ by construction. Compare every
            # scientific result; retain the hash of each native input artifact.
            managed_paths=count.pop('paths')
            direct_paths=repeated.pop('paths')
            assert set(managed_paths)==set(direct_paths) and count==repeated
            assert count['counts']==run['counts'] and count['per_reference']==run['per_reference']
            runs.append(dict(id=run['id'],scope=run['population'],input=run['input_pairs'],
                             integer_cells=len(parity['integers']),allele_identities=count['allele_identities'],
                             original_report_sha256=sha256_file(cell/run['paths']['report'])))
            evidence[key+'/'+run['id']]=dict(native_manifest=run,direct_parity=parity,installed_recount=count,
                managed_artifacts={k:sha256_file(v) for k,v in managed_paths.items()},direct_artifacts={k:sha256_file(v) for k,v in direct_paths.items()})
        exact=r.target_metrics.total_precise_pe
        summary[key]=dict(exact_prepared=[exact.numerator,exact.denominator],runs=runs)
        if key=='f01':
            assert exact.numerator==50 and exact.denominator==100
            assert r.qc.routing_assigned_reads==r.qc.routing_quarantined_reads==50
            assert r.copies['A'].native.numerator is None and r.copies['A'].precise.numerator is None
            assert 'EDIT_STATE_SELECTIVE_COPY_ROUTING' in r.copies['A'].native.reason_codes
            full=r.anchor_evidence['backend_metrics']['A']['native']
            assert (full['numerator'],full['denominator'])==(50,100)
            summary[key]['result']=read(cell/'qualification.json')
        if key.startswith('alsp'):
            counts=r.anchor_evidence['extension_alleles']['copy2']['counts']
            assert counts=={'exact_wt':8,'intended_snp_retained':7,'intended_snp_converted':6,'other_modification':5,'unresolved':0}
            full=r.anchor_evidence['backend_metrics']['copy1']['native']
            assert (full['numerator'],full['denominator'])==(22,35)
            summary[key]['result']=read(base/'alsp01/qualification.json')[key.split('-')[1]]
        if key=='hibit':
            truth=read(base/'hibit03/qualification.json')
            assert [exact.numerator,exact.denominator]==truth['exact_prepared_observed']==[7,15]
            actual=r.anchor_evidence['backend_metrics']['A']
            assert actual['insertion_products']['counts']==truth['aligned_allele_counts']
            assert [actual['native'][v] for v in ('numerator','denominator')]==truth['full_sample_native']==[27,35]
            info=verify_analysis_output(prep).manifest['samples']['1B']
            observed=Counter()
            for pair in paired_fastq(*(prep/info['files'][mate]['path'] for mate in ('r1','r2'))):
                state=read_id(pair[0],1).decode().split(':')[0]
                call=assess_pair(pair,targets)
                observed[state,call['canonical'],call['reason']]+=1
            assert observed==Counter({(state,row['call'],row['reason']):row['n'] for state,rows in
                                       truth['paired_calls'].items() for row in rows})
            summary[key]['result']=truth
    output.mkdir(exist_ok=False,parents=True)
    evidence_bytes=json.dumps(evidence,indent=2,sort_keys=True).encode()
    with (output/'native-evidence.json.gz').open('xb') as out:
        with gzip.GzipFile(filename='',fileobj=out,mode='wb',mtime=0) as gz: gz.write(evidence_bytes)
    wheel,=(package/'dist').glob('*.whl')
    results=dict(commit=(package/'tested-commit').read_text().strip(),wheel=wheel.name,wheel_sha256=sha256_file(wheel),
                 verified_source_sha256=source_hashes,cells=summary,managed_direct_runs=len(evidence),
                 receipt_sha256=sha256_file(output/'native-evidence.json.gz'))
    (output/'result.json').write_text(json.dumps(results,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('base','package','output'):p.add_argument(name,type=Path)
    a=p.parse_args();recount(a.base,a.package,a.output)
