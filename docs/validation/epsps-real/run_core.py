"""Run the digest-pinned CRISPResso wrapper on paired reads prepared by audit.py."""
import argparse
import shutil
import subprocess
from pathlib import Path

from audit import COPY_NAMES, validate_sources, sha, json_write

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('inputs', type=Path)
parser.add_argument('work', type=Path)
parser.add_argument('population', choices=['1A', 'all_known'])
args = parser.parse_args()
base = args.work.resolve()
refs = validate_sources(args.inputs)[1]['EPSPS_284bp']
core = shutil.which('peanalyzer-crispresso')
if not core:
    raise RuntimeError('Activate the editable development environment for PEAnalyzer')
version = subprocess.check_output([core, '--version'], text=True).strip()
assert version == 'CRISPResso 2.3.4'
name = args.population
if (base / ('CRISPResso_on_' + name)).exists():
    raise FileExistsError('Use a new audit directory for a new Core run')
command = ['--fastq_r1', name + '.1.fq', '--fastq_r2', name + '.2.fq',
           '--amplicon_seq', ','.join(refs[c]['wt_sequence'] for c in COPY_NAMES),
           '--amplicon_name', ','.join(COPY_NAMES), '--name', name,
           '--quantification_window_coordinates', '146-146_157-157,146-146_157-157',
           '--keep_intermediate', '--write_detailed_allele_table', '--suppress_report', '--suppress_plots']
with (base / (name + '.core.log')).open('x') as log:
    subprocess.run([core, *command], cwd=base, stdout=log, stderr=subprocess.STDOUT, check=True)
json_write(base / (name + '.command.json'),
           {'version': version, 'argv': command, 'input_hashes': {f: sha(base / f) for f in (command[1], command[3])}})
