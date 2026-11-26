"""Measure the independently audited prepared F-01 fixture, preserving its physical partition."""
import argparse
import json
from pathlib import Path

from peanalyzer.backend.pooled import resolve_executable
from peanalyzer.metrics.production import run_metrics
from peanalyzer.schemas import Target


def main(case, output, executable):
    route=json.loads((case/'routing/routing_manifest.json').read_text())
    targets=[Target.model_validate(t) for t in route['targets']]
    result=run_metrics(analysis_root=case/'prepared',sample_id='1B',targets=targets,analysis_id='F01',
                       output=output,core=resolve_executable(executable),routing_root=case/'routing')
    copy=result.copies['A']
    native=result.anchor_evidence['backend_metrics']['A']['native']
    assert (native['backend_input_reads'], native['numerator'],native['denominator'])==(100,50,100)
    assert (result.target_metrics.total_precise_pe.numerator,result.target_metrics.total_precise_pe.denominator)==(50,100)
    assert (result.qc.routing_assigned_reads,result.qc.routing_quarantined_reads)==(50,50)
    assert copy.native.numerator is None and 'EDIT_STATE_SELECTIVE_COPY_ROUTING' in copy.native.reason_codes
    assert copy.precise.numerator is None and copy.native.confident_input_reads==50
    summary=dict(input_truth={'WT':50,'PE':50},assigned={'WT':50,'PE':0},quarantined={'WT':0,'PE':50},
                 full_sample_native=dict(PE=native['numerator'],aligned=native['denominator'],input=native['backend_input_reads']),
                 exact=[result.target_metrics.total_precise_pe.numerator,result.target_metrics.total_precise_pe.denominator],
                 copy_native=copy.native.status,copy_precise=copy.precise.status,copy_reasons=copy.native.reason_codes,
                 observed_geometry=result.anchor_evidence['copy_routing_eligibility'])
    (output/'qualification.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('case',type=Path);p.add_argument('output',type=Path);p.add_argument('core')
    a=p.parse_args();main(a.case,a.output,a.core)
