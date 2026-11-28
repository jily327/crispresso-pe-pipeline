"""Replay a published native execution with direct Docker and compare its scientific integers.

python direct_parity.py CELL RUN_ID NEW_DIRECTORY
Outputs remain outside the published cell. No PEAnalyzer imports or workflow calls.
"""
import argparse
import csv
import hashlib
import io
import json
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path

IMAGE = 'pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c'
CORE = '/CRISPResso2/.pixi/envs/default/bin/CRISPResso'


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def integer(value):
    if type(value) is int and value >= 0 or isinstance(value, str) and value.isdecimal():
        return int(value)
    raise ValueError(f'Expected a nonnegative integer, got {value!r}')


def evidence(info):
    data = json.loads(info.read_text())
    running, results = data['running_info'], data['results']
    assert running['version'] == '2.3.4' and running['end_time_string']
    counts = {}
    for role, name in [('mapping', 'mapping_stats_filename'), ('quantification', 'quant_of_editing_freq_filename')]:
        with (info.parent/running[name]).open() as f:
            rows = list(csv.DictReader(f, delimiter='\t'))
        for row in rows:
            prefix = role + '/' + (row.get('Amplicon','all')) + '/'
            counts.update({prefix+k:integer(v) for k,v in row.items() if '%' not in k and k != 'Amplicon'})
    for field, values in results['alignment_stats'].items():
        if field.startswith('counts_') or field == 'class_counts':
            counts.update({f'json/{field}/{label}':integer(n) for label,n in values.items()})
    alleles = Counter()
    with zipfile.ZipFile(info.parent/running['allele_frequency_table_zip_filename']) as z:
        with z.open(running['allele_frequency_table_filename']) as buf:
            for row in csv.DictReader(io.TextIOWrapper(buf), delimiter='\t'):
                n = integer(row.pop('#Reads'))
                row.pop('%Reads')
                alleles[tuple(sorted(row.items()))] += n
    args = running['args']['value']
    return dict(counts=counts, alleles=alleles, args=args, refs=[
        (name, results['refs'][name]['sequence'], results['refs'][name]['include_idxs'])
        for name in results['ref_names']])


def replay(cell, run_id, out):
    cell, out = cell.resolve(), out.resolve()
    if out.exists() or out.is_relative_to(cell):
        raise ValueError('Use a new output directory outside the scientific workspace')
    doc = json.loads((cell/'native_runs.json').read_text())
    run, = [r for r in doc['runs'] if r['id'] == run_id]
    if run['execution_status'] != 'COMPLETED' or run['extraction_status'] != 'PASS':
        raise ValueError('Managed native execution and extraction required')
    out.mkdir()
    paths = {k:(cell/v).resolve(strict=True) for k,v in run['paths'].items()}
    if any(not p.is_relative_to(cell) for p in paths.values()):
        raise ValueError('Path outside cell')
    for k,digest in run['sha256'].items():
        if sha(paths[k]) != digest:
            raise ValueError(f'Managed artifact changed: {k}')
    image = json.loads(subprocess.check_output(['docker','image','inspect',IMAGE]))[0]
    version = subprocess.check_output(['docker','run','--rm','--network','none','--entrypoint',CORE,IMAGE,'--version'],
                                      text=True, stderr=subprocess.STDOUT).strip()
    assert IMAGE in image['RepoDigests'] and version.splitlines()[-1] == 'CRISPResso 2.3.4'
    with (out/'direct.log').open('w') as log:
        subprocess.run(['sh',str(paths['script']),str(out/'replay')],stdout=log,stderr=subprocess.STDOUT,check=True)
    direct, = (out/'replay').rglob('CRISPResso2_info.json')
    for k in ('r1','r2'):
        assert sha(out/'replay'/paths[k].name) == run['sha256'][k]
    a,b = evidence(paths['info']),evidence(direct)
    table = []
    for key in sorted(a['counts'].keys() | b['counts'].keys()):
        before, after = a['counts'].get(key), b['counts'].get(key)
        table.append(dict(metric=key, managed=before, direct=after,
                          difference=after-before if None not in (after,before) else None))
    equal_alleles = a['alleles'] == b['alleles']
    equal_args = a['args'] == b['args']
    equal_refs = a['refs'] == b['refs']
    delta = [dict(identity=dict(k), managed=a['alleles'][k],direct=b['alleles'][k])
             for k in a['alleles'].keys() | b['alleles'].keys() if a['alleles'][k] != b['alleles'][k]]
    receipt = run.get('runtime_receipt', {})
    runtime_match = (run.get('runtime_identity_status') == 'VERIFIED' and receipt.get('image_id') == image['Id']
                     and receipt.get('image') == IMAGE and receipt.get('core') == CORE)
    counts_match = all(x['difference'] == 0 for x in table) and equal_alleles and equal_args and equal_refs
    passed = counts_match and runtime_match
    report = dict(id=run_id,sample=doc['sample_id'],target=doc['target_name'],population=run['population'],
                  input_pairs=run['input_pairs'],input_sha256=[run['sha256'][k] for k in ('r1','r2')],
                  script_sha256=run['sha256']['script'],managed_info_sha256=sha(paths['info']),
                  direct_info_sha256=sha(direct),runtime_version=version,image=image['Id'],digest=IMAGE,
                  runtime_match=runtime_match, count_parity=counts_match, managed_runtime_receipt=receipt,
                  status='PASS' if passed else 'FAIL',integers=table,allele_identities=len(a['alleles']),
                  allele_abundance=sum(a['alleles'].values()),alleles_equal=equal_alleles,allele_differences=delta,
                  reference_order_sequences_and_windows_equal=equal_refs,effective_arguments_equal=equal_args,
                  differing_parameters=sorted(k for k in a['args'].keys() | b['args'].keys() if a['args'].get(k)!=b['args'].get(k)))
    (out/'parity.json').write_text(json.dumps(report,indent=2)+'\n')
    print(run_id, report['status'], len(table), 'integer fields;', len(a['alleles']), 'allele identities')
    return passed


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('cell',type=Path)
    p.add_argument('run_id')
    p.add_argument('new_directory',type=Path)
    args=p.parse_args()
    sys.exit(0 if replay(args.cell,args.run_id,args.new_directory) else 1)
