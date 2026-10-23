"""Independent JSON Schema and source/wheel scientific-output qualification.

Run with an evidence environment containing jsonschema (not a pipeline dependency).
"""
import argparse
import json
import shutil
from pathlib import Path
import sys

import jsonschema

REPO=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO/'tests'))
from test_m7_integration import science


def main():
    parser=argparse.ArgumentParser()
    for name in ('source','wheel','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    schema_root=REPO/'src/peanalyzer/workflow_resources'
    schemas={name:json.loads((schema_root/(name+'_manifest.schema.json')).read_text()) for name in ('stage','workflow')}
    for schema in schemas.values():jsonschema.Draft202012Validator.check_schema(schema)
    checked=0
    for base in (args.source,args.wheel):
        for mode in ('clean','resumed','analyze'):
            root=base/'m7'/mode
            for path in [root/'workflow_manifest.json',*sorted((root/'workflow/stages').glob('*.json'))]:
                schema=schemas['workflow' if path.name=='workflow_manifest.json' else 'stage']
                value=json.loads(path.read_text());jsonschema.validate(value,schema);checked+=1
                altered=dict(value,unexpected=True)
                try:jsonschema.validate(altered,schema)
                except jsonschema.ValidationError:pass
                else:raise AssertionError('extra field accepted')
    left,right=args.source/'m7/clean',args.wheel/'m7/clean'
    for relative in ['workflow_manifest.json','workflow/plan.json',
                     *[str(p.relative_to(left)) for p in sorted((left/'workflow/stages').glob('*.json'))]]:
        destination=out/'examples'/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(left/relative,destination)
    assert science(left)==science(right)
    input_hashes={}
    from hashlib import sha256
    for path in sorted((args.source/'m7/inputs').iterdir()):
        twin=args.wheel/'m7/inputs'/path.name
        assert path.read_bytes()==twin.read_bytes()
        input_hashes[path.name]=sha256(path.read_bytes()).hexdigest()
    for label,base in [('source',args.source),('wheel',args.wheel)]:
        (out/(label+'-workflow.json')).write_bytes((base/'m7/qualification.json').read_bytes())
    evidence=dict(status='PASS',independent_json_schema_checks=checked,unknown_fields_rejected=True,
        source_wheel_science_equal=True,synthetic_input_bytes_equal=True,input_sha256=input_hashes,
        compared=['M4 target/copy/QC/eligibility/derived/product evidence','M5 observations/groups/contrasts/families',
                  'prepared FASTQ records','routing FASTQ records and TSV ledgers','M6 SVG bytes'],
        exclusions=['M4/M5 population_id and source_result_sha256: existing root-bound lineage',
                    'backend logs/timestamps/artifact hashes and source paths',
                    'workflow timestamps/sessions and Git source-vs-installed identity',
                    'M6 exact local M5 copy and HTML/TSV source identity; not cross-root byte-identical'])
    (out/'workflow-parity.json').write_text(json.dumps(evidence,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(status='PASS',schema_checks=checked)))

if __name__=='__main__':main()
