"""Reproduce historical PE geometry and all 475 original product decisions."""
import importlib.util
import json
from pathlib import Path
import sys
from peanalyzer.remediation import qualify_indels
from peanalyzer.fastq import paired_fastq,read_id
from peanalyzer.observability import assess_pair
from peanalyzer.schemas import Target

repo=Path(__file__).resolve().parents[3];out=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('single_copy_panels',repo/'docs/validation/readthrough-singlecopy/panels.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
import peanalyzer.routing as routing
single=module.grid(routing)
assert single==json.loads((repo/'docs/validation/readthrough-singlecopy/baseline-070.json').read_text())
multi=qualify_indels()
assert multi==json.loads((repo/'docs/validation/readthrough/geometry-grid.json').read_text())
assert sum(r['geometry_status']!='BLOCKED' for r in multi)==13
baseline=Path('/workspace/validation/readthrough-singlecopy/source-final/m4')
current=Path(sys.argv[1])/'m4'
trials={}
for kind in ('m3','m31'):
    old,new=baseline/kind,current/kind
    raw=json.loads((new/'m4/result.json').read_text())
    targets=[Target.model_validate(t) for t in raw['product_evidence']['target']['targets']]
    def decisions(root):
        manifest=json.loads((root/'analysis/analysis_manifest.json').read_text())
        sample=manifest['samples']['1B']
        paths=[root/'analysis'/sample['files'][f'r{i}']['path'] for i in (1,2)]
        return {read_id(pair[0],1).decode():dict(records=[r.to_bytes().hex() for r in pair],assessment=assess_pair(pair,targets)) for pair in paired_fastq(*paths)}
    before,after=decisions(old),decisions(new)
    assert before==after
    trials[kind]=dict(pairs=len(after),changed_records=0,changed_assessments=0)
assert sum(r['pairs'] for r in trials.values())==475
result=dict(single_copy=dict(panels=72,allowed=15,blocked=57,trial_decisions=432,changed=0),
    multi_copy=dict(designs=36,allowed=13,blocked=23,trial_decisions=432,changed=0),historical_products=trials)
(out/'pe-routing-and-products.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps(result))
