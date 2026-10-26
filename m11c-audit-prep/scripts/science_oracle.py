"""Independent scientific projection with explicit provenance-only exclusions."""
import argparse,gzip,hashlib,zipfile
from pathlib import Path
from common import read,sha,digest,write

# These identifiers hash root-bound source manifests, not biological values.
PROVENANCE_KEYS={'population_id','source_result_sha256'}
def scientific(value):
    if isinstance(value,dict):return {k:scientific(v) for k,v in value.items() if k not in PROVENANCE_KEYS}
    if isinstance(value,list):return [scientific(v) for v in value]
    return value

def capture(root):
    root=Path(root);plan=read(root/'workflow/plan.json');manifest=read(root/'workflow_manifest.json')
    metrics={};child_payloads={}
    def metric(p):
        m=read(p);provenance=m.pop('provenance')
        excluded={'software','prepared_manifest_sha256','routing_manifest_sha256','artifacts','execution'}
        allowed=excluded|{'prepared_sample','target_definitions_sha256','routing_policy_identity','crispresso_version','runtime_digest','analysis_mode','wt_sha256','scientific_identity'}
        assert not set(provenance)-allowed, 'Unknown provenance field requires review'
        # Retain every scientific provenance field. Excluded artifact hashes still
        # must match their exact local files; Core scientific tables are compared below.
        for name,entry in provenance.get('artifacts',{}).items():
            expected=entry['sha256'] if isinstance(entry,dict) else entry
            parts=Path(name).parts
            if parts[0]=='prepared':actual=root/'analysis'/Path(*parts[1:])
            elif parts[0]=='routing':actual=root/'routing'/p.parent.parent.name/p.parent.name/Path(*parts[1:])
            elif parts[0] in ('anchors','copies'):
                base=p.parent/('comparator' if parts[0]=='anchors' else 'copies')/parts[1]
                if parts[2]=='child':
                    candidates=list((base/'output').glob('*/'+parts[3]));assert len(candidates)==1;actual=candidates[0]
                else:actual=base/Path(*parts[2:])
            else:actual=p.parent/name
            assert sha(actual)==expected
        for mate,entry in provenance['prepared_sample']['files'].items():
            assert sha(root/'analysis'/entry['path'])==entry['sha256']
        assert sha(p.parent/'prepared/analysis_manifest.json')==provenance['prepared_manifest_sha256'] if (p.parent/'prepared/analysis_manifest.json').exists() else sha(root/'analysis/analysis_manifest.json')==provenance['prepared_manifest_sha256']
        if 'routing_manifest_sha256' in provenance:assert sha(root/'routing'/p.parent.parent.name/p.parent.name/'routing_manifest.json')==provenance['routing_manifest_sha256']
        m['scientific_provenance']={k:v for k,v in provenance.items() if k not in excluded}
        if m.get('analysis_mode')=='indel_nuclease':
            identity=provenance['scientific_identity'];settings=identity['backend_settings']
            assert len(settings)==58 and provenance['execution']['scientific_identity']==identity
            info=read(next(p.parent.rglob('CRISPResso2_info.json')))
            assert all(info['running_info']['args']['value'][k]==v for k,v in settings.items())
        return scientific(m)
    for p in sorted((root/'metrics').rglob('result.json')):
        metrics[p.relative_to(root/'metrics').as_posix()]=metric(p)
    for p in sorted((root/'metrics').rglob('*')):
        if p.name=='Alleles_frequency_table.zip':
            with zipfile.ZipFile(p) as archive:
                for name in sorted(archive.namelist()):child_payloads[p.relative_to(root/'metrics').as_posix()+'!'+name]=hashlib.sha256(archive.read(name)).hexdigest()
        elif p.name in ('CRISPResso_mapping_statistics.txt','CRISPResso_quantification_of_editing_frequency.txt'):
            child_payloads[p.relative_to(root/'metrics').as_posix()]=sha(p)
    statistics=read(root/'statistics/result.json')
    # Validate each lineage hash against its actual local source before exclusion.
    for item in statistics['provenance']['input_results']:
        assert item['sha256']==sha(root/'metrics'/item['source_result'])
    assert statistics['input_manifest_hash']==sha(root/'metrics/manifest.csv')
    assert statistics['sample_metadata_hash']==plan['inputs']['samples']['sha256']
    assert (root/'report/source/result.json').read_bytes()==(root/'statistics/result.json').read_bytes()
    report=read(root/'report/report_manifest.json');assert report['source_result_sha256']==sha(root/'statistics/result.json')
    for item in plan['inputs'].values():
        assert sha(item['source_path'])==item['sha256']
        if item['snapshot']:assert sha(root/item['snapshot'])==item['sha256']
    # M5 embeds complete nuclease results; require exact local-source identity before
    # excluding the same execution provenance already excluded from standalone metrics.
    local_nuclease=[read(p) for p in sorted((root/'metrics').rglob('result.json')) if read(p).get('analysis_mode')=='indel_nuclease']
    assert statistics.get('nuclease_results',[])==local_nuclease
    statistics['nuclease_results']=[metric(p) for p in sorted((root/'metrics').rglob('result.json')) if read(p).get('analysis_mode')=='indel_nuclease']
    statistics.pop('provenance')
    values=dict(samples=plan['samples'],targets=plan['targets'],scientific_options=plan['normalized_options'],
        input_hashes={k:dict(sha256=v['sha256'],size_bytes=v['size_bytes']) for k,v in plan['inputs'].items()},
        metrics=metrics,child_scientific_tables=child_payloads,statistics=scientific(statistics),stage_statuses={},payloads={},figures={})
    for k,v in manifest['stage_inventory'].items():
        stage=read(root/v['path']);values['stage_statuses'][k]=dict(status=stage['status'],reasons=stage['reason_codes'])
    for family in ('analysis','routing'):
        for p in sorted((root/family).rglob('*')):
            if p.is_file() and p.name.endswith('.fastq.gz'):
                values['payloads'][p.relative_to(root).as_posix()]=hashlib.sha256(gzip.decompress(p.read_bytes())).hexdigest()
            elif p.is_file() and p.name in ('routing_ledger.jsonl','scientific_gate.json'):
                values['payloads'][p.relative_to(root).as_posix()]=sha(p)
    for p in sorted((root/'report/figures').glob('*.svg')):values['figures'][p.name]=sha(p)
    return values

def compare(a,b):
    x,y=capture(a),capture(b)
    differences=[key for key in sorted(set(x)|set(y)) if x.get(key)!=y.get(key)]
    return dict(equal=not differences,differing_categories=differences,left_sha256=digest(x),right_sha256=digest(y),
        exclusions=['metric.provenance software/execution and locally verified artifact/prepared/routing hashes only; scientific provenance retained','statistics.provenance (source hashes independently verified)','statistics.nuclease_results[].provenance (exact local metric copies verified; scientific identity retained)',
                    'population_id','source_result_sha256','gzip header timestamps; decompressed payloads compared'],
        report_source_lineage_valid=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('fresh');p.add_argument('recovery');p.add_argument('--out',required=True);a=p.parse_args()
    result=compare(a.fresh,a.recovery);write(a.out,result)
    if not result['equal']:raise SystemExit(1)
