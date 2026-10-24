"""Verify completed real workflows and record compact, inspectable integer evidence."""
import argparse,csv,hashlib,json
from pathlib import Path
from xml.etree import ElementTree as ET
from peanalyzer.metrics.models import MetricResult
from peanalyzer.statistical_models import StatisticsResult
from peanalyzer.reporting_models import ReportManifest
from peanalyzer.workflow import verify_workflow_output

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('dataset');p.add_argument('root',type=Path);p.add_argument('work',type=Path);a=p.parse_args();out=Path(__file__).resolve().parent
    oracle=json.loads((a.work/(a.dataset+'-oracle.json')).read_text())
    wheel=json.loads((a.work/(a.dataset+'-wheel-oracle.json')).read_text());assert oracle==wheel
    (out/(a.dataset+'-oracle.json')).write_text(json.dumps(oracle,indent=2,sort_keys=True)+'\n')
    wf=verify_workflow_output(a.root)
    result=json.loads((a.root/'statistics/result.json').read_text());stats=StatisticsResult.model_validate(result)
    assert stats.contrasts==[] and not stats.unused_metadata_sample_ids
    report=ReportManifest.model_validate_json((a.root/'report/report_manifest.json').read_bytes())
    assert (a.root/'report/source/result.json').read_bytes()==(a.root/'statistics/result.json').read_bytes()
    assert report.source_result_sha256==sha(a.root/'statistics/result.json')
    html=(a.root/'report/report.html').read_text();svgs=0
    for item in report.artifacts:
        f=a.root/'report'/item.path;assert sha(f)==item.sha256
        if item.artifact_kind=='figure':
            text=f.read_text();ET.fromstring(text);assert text in html;svgs+=1
    counts={};all_metrics={}
    for path in sorted((a.root/'metrics').glob('*/ALSW/result.json')):
        model=MetricResult.model_validate_json(path.read_bytes());r=model.model_dump(mode='json');sid=r['sample_id']
        assert sid==path.parts[-3] and sid in oracle['sample_counts']
        m=r['target_metrics']['total_precise_pe'];truth=oracle['exact_haplotypes'][sid]
        n=truth.get('exact_PE',0);d=n+truth.get('exact_WT',0)
        assert m['status']=='REPORTABLE' and (m['numerator'],m['denominator'])==(n,d)
        assert m['population_input_reads']==oracle['sample_counts'][sid]
        assert m['population_denominator_exclusions']==oracle['sample_counts'][sid]-d
        metrics=list(r['target_metrics'].values())+[metric for copy in r['copies'].values() for metric in copy.values() if isinstance(metric,dict) and 'metric_name' in metric]
        # Exports preserve reportability/counts; no new aggregate arithmetic here.
        for metric in metrics:
            matches=[o for o in stats.observations if o.sample_id==sid and o.metric_name==metric['metric_name']]
            assert len(matches)==1
            o=matches[0];assert (o.status,o.numerator,o.denominator)==(metric['status'],metric['numerator'],metric['denominator'])
        native=r['target_metrics']['target_crispresso_native_pe']
        counts[sid]=dict(input_pairs=oracle['sample_counts'][sid],precise_status=m['status'],exact_wt=truth.get('exact_WT',0),exact_pe=n,precise_denominator=d,excluded=oracle['sample_counts'][sid]-d,precise_percent=100*n/d,native_numerator=native['numerator'],native_denominator=native['denominator'],result_sha256=sha(path))
        all_metrics[sid]=dict(target_metrics=r['target_metrics'],copies=r['copies'])
    assert set(counts)==set(oracle['sample_counts'])=={o.sample_id for o in stats.observations}
    resume=json.loads((a.work/(a.dataset+'-resume.txt')).read_text());assert resume['executed_stages']==[]
    assert resume['workflow_manifest_sha256']==sha(a.root/'workflow_manifest.json')
    result=dict(dataset=a.dataset,workflow_status=wf.status,workflow_manifest_sha256=sha(a.root/'workflow_manifest.json'),software_identity=wf.software_identity.model_dump(),samples=counts,source_wheel_oracle_equal=True,source_copy_exact=True,report_artifact_hashes='PASS',exported_embedded_svg_count=svgs,xml_valid=True,statistics_mode='summarize',sample_metadata_records_including_controls=len(counts),observations=len(stats.observations),zero_execution_resume=resume)
    (out/(a.dataset+'-results.json')).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    (out/(a.dataset+'-metrics.json')).write_text(json.dumps(all_metrics,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(dataset=a.dataset,status=wf.status,samples=len(counts),svgs=svgs)))
if __name__=='__main__':main()
