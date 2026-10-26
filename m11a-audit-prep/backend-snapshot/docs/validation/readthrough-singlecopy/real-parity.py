"""Exhaustive current-router replay against immutable candidate real-data evidence."""
import argparse,hashlib,json
from collections import Counter
from itertools import zip_longest
from pathlib import Path
from peanalyzer.fastq import paired_fastq
from peanalyzer.geometry import geometry
from peanalyzer.routing import route_pair,RoutingPolicy
from peanalyzer.observability import assess_pair
from peanalyzer.metrics.products import product_counts
from peanalyzer.metrics.models import MetricResult
from peanalyzer.workflow import verify_workflow_output
from peanalyzer.demux_verify import sha256_file
from peanalyzer.schemas import Target

p=argparse.ArgumentParser();p.add_argument('dataset');p.add_argument('root',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
manifest=json.loads((a.root/'analysis/analysis_manifest.json').read_text())
rows={};losses=[]
previous=Path(__file__).resolve().parents[1]/'readthrough'
expected_results=json.loads((previous/(a.dataset+'-results.json')).read_text())
loss_ids={x['id_sha256'] for x in json.loads((previous/'AmpSeq-conservative-losses.json').read_text())} if a.dataset=='AmpSeq' else set()
labels={'exact_WT':'exact_wt','exact_PE':'exact_pe','state_collision':'contradictory_state','other_or_unassessable':'unresolved_unassessable'}
for sample,item in sorted(manifest['samples'].items()):
    route_root=a.root/f'routing/{sample}/ALSW';routed=json.loads((route_root/'routing_manifest.json').read_text())
    targets=[Target.model_validate(x) for x in routed['targets']];assert len(targets)==2
    report=geometry(targets);counts=Counter();reasons=Counter();digest=hashlib.sha256();n=0
    with (route_root/'routing_ledger.jsonl').open() as ledger:
        for pair,line in zip_longest(paired_fastq(*(a.root/'analysis'/item['files'][f'r{m}']['path'] for m in (1,2))),ledger):
            assert pair and line
            actual=route_pair(pair,targets,report,RoutingPolicy())
            serialized=json.dumps(actual,sort_keys=True)+'\n'
            assert serialized==line,(a.dataset,sample,actual['read_id'])
            digest.update(serialized.encode());n+=1
            assessment=assess_pair(pair,targets);counts[labels[assessment['canonical']]]+=1
            if assessment['reason']:reasons[assessment['reason']]+=1
            identifier_hash=hashlib.sha256(actual['read_id'].encode()).hexdigest()
            if identifier_hash in loss_ids:
                assert actual['assigned_copy'] is None and actual['category']=='ALIGNMENT_FAILURE'
                losses.append(dict(sample=sample,id_sha256=identifier_hash,category=actual['category'],reason=actual['reason']))
    product=product_counts(counts);product.exclusion_reason_counts=dict(reasons)
    path=a.root/f'metrics/{sample}/ALSW/result.json';result=MetricResult.model_validate_json(path.read_bytes())
    assert result.target_metrics.total_precise_pe.products==product
    assert sha256_file(path)==expected_results['samples'][sample]['result_sha256']
    assert n==item['pairs'] and digest.hexdigest()==sha256_file(route_root/'routing_ledger.jsonl')
    rows[sample]=dict(pairs=n,routing_ledger_sha256=digest.hexdigest(),routing_rows_byte_identical=True,exact_product_counts_identical=True,metric_result_sha256=sha256_file(path),precise_numerator=product.exact_pe,precise_denominator=product.exact_pe+product.exact_wt)
    print(a.dataset,sample,n,'routing and product parity PASS',flush=True)
if a.dataset=='AmpSeq':assert len(losses)==1
before=sha256_file(a.root/'workflow_manifest.json');verified=verify_workflow_output(a.root)
assert verified.status=='COMPLETED' and sha256_file(a.root/'workflow_manifest.json')==before==expected_results['workflow_manifest_sha256']
assert (a.root/'report/source/result.json').read_bytes()==(a.root/'statistics/result.json').read_bytes()
report=json.loads((a.root/'report/report_manifest.json').read_text())
for artifact in report['artifacts']:assert sha256_file(a.root/'report'/artifact['path'])==artifact['sha256']
a.output.write_text(json.dumps(dict(dataset=a.dataset,pairs=sum(x['pairs'] for x in rows.values()),changed_routing_rows=0,changed_product_counts=0,unchanged_result_files=len(rows),workflow_manifest_sha256=before,completed_workflow_verified=True,report_hashes_valid=True,source_copy_exact=True,internal_deletion_quarantine=losses,samples=rows,backend_reexecuted=False),indent=2,sort_keys=True)+'\n')
print(a.dataset,'full parity PASS',flush=True)
