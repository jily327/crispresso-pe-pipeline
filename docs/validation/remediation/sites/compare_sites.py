"""Compare derived site integers to the actual pinned Core allele tables for each population."""
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

from peanalyzer.backend.intended_sites import read_core_sites


def panel(archive):
    with ZipFile(archive) as bundle:
        pi = next(p for p in json.loads(bundle.read('reference_manifest.json'))['reference_panels'] if p['panel_id']=='EPSPS_284bp')
        return [SimpleNamespace(copy_name=c['copy_id'], wt_sequence=c['wt_sequence'], prime_edited_sequence=c['intended_pe_sequence']) for c in pi['reference_copies']]


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference',type=Path)
    parser.add_argument('runs',nargs='+',help='name=/path/to/CRISPResso_on...')
    args=parser.parse_args()
    output={}
    for spec in args.runs:
        name, directory=spec.split('=',1)
        path=Path(directory)
        report=read_core_sites(path,panel(args.reference))
        output[name]={k: report[k] for k in ('combined','input_pairs','preprocessed','aligned','ambiguous','discarded','backend_reference')}
        output[name]['alleles_sha256']=hashlib.sha256((path/'Alleles_frequency_table.zip').read_bytes()).hexdigest()
    print(json.dumps(output,indent=2,sort_keys=True))
