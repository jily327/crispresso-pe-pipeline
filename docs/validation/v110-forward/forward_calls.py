"""Reclassify identified M3/M3.1 forward paired FASTQs using the imported package."""
import argparse
import csv
import json
from pathlib import Path

from peanalyzer.fastq import paired_fastq, read_id
from peanalyzer.geometry import geometry
from peanalyzer.observability import assess_pair
from peanalyzer.routing import RoutingPolicy, route_pair
from peanalyzer.schemas import Target


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('runs',type=Path)
    p.add_argument('output',type=Path)
    args=p.parse_args()
    with args.output.open('x',newline='') as f:
        writer=csv.writer(f)
        writer.writerow(['fixture','read_id','canonical','category','assigned_copy'])
        for name, filename in [('m3','synthetic_design.json'),('m31','targets.json')]:
            root=args.runs/name
            definitions=json.loads((root/'synthetic'/filename).read_bytes())
            if name=='m3':
                definitions=definitions['targets']
            targets=[Target.model_validate(t) for t in definitions]
            gate=geometry(targets)
            sample=json.loads((root/'analysis/analysis_manifest.json').read_bytes())['samples']['1B']
            paths=[root/'analysis'/sample['files'][f'r{i}']['path'] for i in (1,2)]
            for pair in paired_fastq(*paths):
                scientific=assess_pair(pair,targets)
                routed=route_pair(pair,targets,gate,RoutingPolicy()) if name=='m31' else {}
                writer.writerow([name,read_id(pair[0],1).decode(),scientific['canonical'],routed.get('category'),routed.get('assigned_copy')])


if __name__=='__main__':
    main()
