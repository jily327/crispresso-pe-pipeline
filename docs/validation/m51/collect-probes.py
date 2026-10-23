"""Record source/wheel scientific and same-input publication byte parity."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def main():
    parser=argparse.ArgumentParser()
    for name in ('source','wheel','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    source=json.loads((args.source/'report.json').read_text())
    wheel=json.loads((args.wheel/'report.json').read_text())
    assert source==wheel
    compared={}
    for path in sorted(args.source.rglob('*')):
        if not path.is_file() or path.name=='report.json':continue
        relative=path.relative_to(args.source)
        assert path.read_bytes()==(args.wheel/relative).read_bytes(),relative
        compared[str(relative)]=dict(byte_identical=True,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    assert len(compared)==16
    for name,root in [('source',args.source),('wheel',args.wheel)]:
        shutil.copyfile(root/'report.json',args.output/(name+'-probes.json'))
    proof=dict(status='PASS',probe_reports_equal=True,complete_parent_scientific_parity=True,
        artifacts=compared,compared_artifacts=16,comparison_includes_provenance=True,
        basis='Identical synthetic fixture paths and bytes; Python/platform and package versions agree.')
    (args.output/'source-wheel-parity.json').write_text(json.dumps(proof,indent=2,sort_keys=True)+'\n')
    print('PASS: source/wheel probe reports and 16 full published artifacts are identical')


if __name__=='__main__':main()
