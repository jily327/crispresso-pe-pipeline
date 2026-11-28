"""Emit per-read calls to a fresh path. Run once under frozen v1.0.1 and once under the candidate."""
import argparse
import csv
import gzip
from collections import defaultdict
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

from peanalyzer.fastq import paired_fastq
from peanalyzer.observability import assess_pair

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'epsps-real'))
from audit import validate_sources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('attachment_dir', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--oracle', action='store_true', help='Use the independent archived coordinate oracle')
    args = parser.parse_args()
    paths, refs = validate_sources(args.attachment_dir)
    archive = runpy.run_path(str(Path(__file__).resolve().parents[1]/'readthrough/recount.py')) if args.oracle else None
    panels = {}
    for name, trim in [('ALSW_211bp',69),('ALSW_253bp',27)]:
        targets = [SimpleNamespace(copy_name=key, wt_sequence=row['wt_sequence'],
                        prime_edited_sequence=row['intended_pe_sequence']) for key,row in refs[name].items()]
        states = defaultdict(set)
        for t in targets:
            states[t.wt_sequence].add('exact_WT')
            states[t.prime_edited_sequence].add('exact_PE')
        panels[name] = targets, trim, states
    files=[paths[f'ALSW_dif_knots_R{mate}.fastq.gz'] for mate in (1,2)]
    with gzip.open(args.output, 'xt', newline='') as stream:
        out=csv.writer(stream)
        out.writerow(['panel','pairs_seen','product','reason'])
        for index, (left,right) in enumerate(paired_fastq(*files),1):
            for name, (targets, trim, states) in panels.items():
                if len(left.sequence)<=trim or len(right.sequence)<=27:
                    out.writerow([name,index,'not_assessable','READ_TOO_SHORT_FOR_PANEL_HYPOTHESIS'])
                    continue
                if archive:
                    state = archive['oracle'](left.sequence[trim:].decode().upper(),
                        archive['rc'](right.sequence[27:].decode().upper()), states)
                    out.writerow([name,index,state,''])
                    continue
                result=assess_pair((left.trimmed(trim),right.trimmed(27)),targets)
                out.writerow([name,index,result['canonical'],result['reason'] or ''])


if __name__=='__main__':
    main()
