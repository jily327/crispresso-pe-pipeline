"""Synthetic strand equivalence and editable-marker challenge; the original ALSP run is pending."""
import argparse
import importlib.util
import json
from pathlib import Path

from peanalyzer.analysis_verify import verify_analysis_output
from peanalyzer.backend.native_runs import write_native_runs
from peanalyzer.backend.pooled import resolve_executable
from peanalyzer.metrics.production import run_metrics
from peanalyzer.routing import route_analysis
from peanalyzer.schemas import Target, reverse_complement


def main(root, executable):
    source=Path(__file__).resolve().parents[2]/'pe-normalization/reproduce_extension.py'
    spec=importlib.util.spec_from_file_location('extension_fixture',source)
    make=importlib.util.module_from_spec(spec);spec.loader.exec_module(make)
    make.main(root,executable)
    original=json.loads((root/'routing/routing_manifest.json').read_text())
    forward=[Target.model_validate(t) for t in original['targets']]
    reverse=[t.model_copy(update=dict(wt_sequence=reverse_complement(t.wt_sequence),
                 prime_edited_sequence=reverse_complement(t.prime_edited_sequence))) for t in forward]
    route_analysis(root/'prepared','1B',reverse,root/'reverse_routing')
    run_metrics(analysis_root=root/'prepared',sample_id='1B',targets=reverse,analysis_id='ALSP-reverse-synthetic',
                output=root/'reverse_metrics',core=resolve_executable(executable),routing_root=root/'reverse_routing')
    sample=verify_analysis_output(root/'prepared').manifest['samples']['1B']
    summary={}
    for case,panel,route,metric in [('forward',forward,'routing','metrics'),('reverse',reverse,'reverse_routing','reverse_metrics')]:
        data=json.loads((root/metric/'result.json').read_text())
        write_native_runs(root/metric,'1B',panel[0].target_name,panel,sample)
        counts=data['anchor_evidence']['extension_alleles']['copy2']['counts']
        assert counts=={'exact_wt':8,'intended_snp_retained':7,'intended_snp_converted':6,'other_modification':5,'unresolved':0}
        ledger=[json.loads(x) for x in (root/route/'routing_ledger.jsonl').read_text().splitlines()]
        assert all(r['assigned_copy']=='copy2' for r in ledger if r['read_id'].startswith('artificial-4-'))
        assert all(r['assigned_copy'] is None for r in ledger if r['read_id'].startswith('artificial-6-'))
        full=data['anchor_evidence']['backend_metrics']['copy1']['native']
        summary[case]=dict(counts=counts,full_sample_anchor_pairs=full['backend_input_reads'],
                           full_sample_native=[full['numerator'],full['denominator']],converted_verified=6,mosaic_quarantined=2)
    assert summary['forward']==summary['reverse']
    (root/'qualification.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('core')
    a=p.parse_args();main(a.output,a.core)
