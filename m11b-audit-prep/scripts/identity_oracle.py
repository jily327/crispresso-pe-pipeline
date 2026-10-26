"""Cross-check frozen Review -> accepted submission -> existing workflow evidence.

Run in a pinned, audited backend environment. accepted.json is an AUDITOR adapter
of the actual captured HTTP request/response, not candidate job JSON alone.
No backend execution. Full lifecycle/race evidence remains separately required.
"""
import argparse,json
from pathlib import Path
from common import read,fields,digest,canonical

def review_science(draft,preview):
    from peanalyzer.gui.setup_models import DraftContent
    from peanalyzer.gui.setup_validation import target_values,MemoryCSV
    from peanalyzer.validation import load_samples,load_targets
    from peanalyzer.barcodes import Catalog,bundled_catalog,load_catalog
    from peanalyzer.workflow import scientific_target
    d=DraftContent.model_validate(draft['content'])
    catalog=load_catalog(bundled_catalog()) if d.library_profile=='qi_hitom_v1' else Catalog([],authoritative=False)
    samples=sorted(load_samples(MemoryCSV([s.model_dump() for s in d.samples],'Frozen draft'),catalog),key=lambda s:s.barcode_id)
    targets=sorted(load_targets(MemoryCSV([{k:'' if v is None else v for k,v in target_values(t).items()} for t in d.targets],'Frozen targets')),key=lambda t:(t.target_name,t.copy_name))
    config=fields(preview['configuration']);backend=fields(preview['backend_identity']);inputs=fields(preview['inputs'])
    assert [s.model_dump() for s in samples]==[v for _,v in sorted(fields(preview['samples']).items())],'draft/Review samples differ'
    from peanalyzer.schemas import Config
    from peanalyzer.routing import RoutingPolicy,policy_identity
    assert config['demux_config']==Config(schema_version=1,demux={'profile':d.library_profile}).model_dump()
    assert config['statistics']=='summarize'
    expected_policy=policy_identity(RoutingPolicy()) if d.analysis_mode=='precise_edit' else 'single_copy_identity'
    assert config['routing_policy']==expected_policy
    for name,value in [('r1_analysis_trim_5p',d.trim_r1),('r2_analysis_trim_5p',d.trim_r2)]:
        if value.strip():assert config['preparation'][name]==int(value)
    normalized=dict(mode=d.analysis_mode,source_mode=d.input_mode,samples=[s.model_dump() for s in samples],
        targets=[scientific_target(t) for t in targets],inputs=inputs,**config,backend=backend)
    assert digest(normalized)==preview['scientific_identity_sha256'],'Review scientific digest differs'
    assert preview['analysis_name']==d.analysis_name
    return normalized

def check(draft,preview,accepted,workspace):
    from peanalyzer.workflow import verify_workflow_output
    from peanalyzer.gui.workspace import snapshot
    root=Path(workspace).resolve();science=review_science(draft,preview)
    for name in ('draft_id','revision'):assert accepted[name]==draft[name],name+' mismatch'
    for name in ('scientific_identity_sha256','plan_identity_sha256'):assert accepted[name]==preview[name],name+' mismatch'
    assert accepted['output']==str(root)
    assert preview['plan_identity_sha256']==digest(dict(scientific_identity=preview['scientific_identity_sha256'],analysis_name=preview['analysis_name'],output=digest(str(root))))
    verify_workflow_output(root)
    plan=read(root/'workflow/plan.json');opts=plan['normalized_options']
    assert plan['mode']==science['source_mode'];assert plan['samples']==science['samples']
    assert opts['scientific_configuration']==science['targets'];assert opts['analysis_modes']==[science['mode']]
    assert opts['demux_config']==science['demux_config'];assert opts['statistics_mode']=='summarize'
    assert not {'contrasts','policies'} & set(plan['inputs'])
    if science['mode']=='precise_edit':assert opts['routing_policy_identity']==science['routing_policy']
    prep=read(root/'analysis/analysis_manifest.json')
    for k,v in science['preparation'].items():assert prep[k]==v,'effective trim mismatch'
    if plan['mode']=='run':
        for role in ('r1','r2'):
            a=plan['inputs'][role];b=science['inputs'][role]
            assert a['sha256']==b['sha256'] and str(a['size_bytes'])==b['size_bytes']
    else:
        assert digest(snapshot(Path(opts['external_demux'])))==science['inputs']['demux']['inventory_sha256']
    backend=plan['backend_identity'];expected=science['backend']
    assert backend['version']==expected['crispresso_required']=='2.3.4'
    assert backend['runtime_digest']==expected['runtime_digest_required']
    assert plan['software_identity']['pipeline_version']==expected['package_version']
    assert (root/'report/source/result.json').read_bytes()==(root/'statistics/result.json').read_bytes()
    return {'review_digest_reconstructed':True,'accepted_identity_matches':True,'workflow_verified':True,'scientific_mapping_matches':True}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('draft');p.add_argument('preview');p.add_argument('accepted');p.add_argument('workspace');a=p.parse_args()
    print(json.dumps(check(read(a.draft),read(a.preview),read(a.accepted),a.workspace),indent=2))
