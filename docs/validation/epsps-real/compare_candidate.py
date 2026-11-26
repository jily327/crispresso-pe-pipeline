"""Exercise the installed candidate CLI, independent of the frozen v1.0.1 reader."""
import argparse
import csv
from collections import Counter
import hashlib
from types import SimpleNamespace
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile

from audit import CATALOG, HERE, STATES, calls, validate_sources
from raw_oracle import epsps


def compare(inputs, out):
    paths, _ = validate_sources(inputs)
    out.mkdir(parents=True, exist_ok=False)
    with ZipFile(paths['ALSW_EPSPS_regression_reference_DNA.zip']) as z:
        fasta = out / 'EPSPS_284bp.fasta'
        fasta.write_bytes(z.read(fasta.name))
    catalogs = calls()
    sheet = out / 'physical-indexes.csv'
    with sheet.open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(('sample_name','barcode_id','forward_barcode_id','reverse_barcode_id'))
        for forward in catalogs[0].values():
            for reverse in catalogs[1].values():
                barcode = forward + reverse
                writer.writerow((barcode, barcode, 'F'+forward, 'R'+reverse))
    config = HERE.parent / 'readthrough/config.yaml'
    archive = out / 'demux'
    with (out / 'demux-result.json').open('w') as f:
        subprocess.run(['peanalyzer', 'demux', '--r1', paths['EPSPS_1106_R1.fastq.gz'],
                        '--r2', paths['EPSPS_1106_R2.fastq.gz'], '--samples', sheet,
                        '--config', config, '--output', archive], stdout=f, check=True)
    with (out / 'candidate.json').open('w') as f:
        subprocess.run(['peanalyzer','haplotypes','--demux-root',archive,'--references',fasta,
                        '--analysis-r1-trim-5p','26','--analysis-r2-trim-5p','27','--negative-control','7G',
                        '--copy-marker-start','99','--copy-marker-start','226'], stdout=f, check=True)
    data = json.loads((out / 'candidate.json').read_text())
    samples = data['samples']
    with (HERE / 'evidence/barcodes.csv').open() as f:
        expected = {r['barcode']: int(r['EPSPS_pairs']) for r in csv.DictReader(f)}
    assert {b: s['input_pairs'] for b,s in samples.items()} == {b:n for b,n in expected.items() if '?' not in b}
    raw = json.loads((out / 'demux-result.json').read_text())
    assert raw['total_input_read_pairs'] == sum(expected.values())
    assert raw['assigned_expected_pair'] == sum(s['input_pairs'] for s in samples.values())
    from peanalyzer.demux_verify import verify_demux_output
    from peanalyzer.fastq import paired_fastq
    from peanalyzer.observability import assess_pair
    refs = validate_sources(inputs)[1]['EPSPS_284bp']
    targets = [SimpleNamespace(copy_name=copy, wt_sequence=r['wt_sequence'],
                               prime_edited_sequence=r['intended_pe_sequence']) for copy, r in refs.items()]
    independent, retention = epsps(paths,CATALOG)
    cell_counts = Counter()
    by_method = {}
    discrepancies = []

    def check(method, barcode, scope, cell, expected, actual):
        labels = ['total', 'nonzero' if expected else 'zero']
        if cell == 'WT':
            labels.append('WT')
        elif cell in ('A_only','B_only','AB','A_numerator','B_numerator'):
            labels.append('edited')
        if scope == 'unresolved':
            labels.append('unresolved')
        subset = by_method.setdefault(method,Counter())
        for key in labels:
            cell_counts[key] += 1
            subset[key] += 1
        if actual != expected:
            discrepancies.append(dict(method=method, barcode=barcode, scope=scope, cell=cell,
                                      expected=expected, actual=actual))

    for sample in verify_demux_output(archive).samples:
        barcode=sample.sample_id
        observed=samples[barcode]
        oracle=independent[barcode]
        for prefix,name in [('joint','two_site_q30'),('full','full_templates')]:
            group=observed[name]
            for scope,record in [('combined',group['combined']),('unresolved',group['unresolved_copy']),*group['copies'].items()]:
                for state in STATES:
                    check(name,barcode,scope,state,oracle[f'{prefix}/{scope}/{state}'],record['counts'][state])
        for label in ('A','B'):
            n=oracle[f'{label}/combined/True']
            for key,expected in [('numerator',n),('denominator',n+oracle[f'{label}/combined/False'])]:
                check('marginal',barcode,'combined',label+'_'+key,expected,observed['two_site_q30']['combined']['site_'+label][key])
        canonical=Counter()
        for records in paired_fastq(sample.r1, sample.r2):
            if len(records[0].sequence)>26 and len(records[1].sequence)>27:
                prepared=tuple(rec.trimmed(n) for rec,n in zip(records,(26,27)))
                canonical[assess_pair(prepared,targets)['canonical']] += 1
        for state,actual in [('WT','exact_WT'),('AB','exact_PE')]:
            check('canonical',barcode,'combined',state,oracle['canonical/'+state],canonical[actual])
    raw_ab = {b:dict(raw_pairs=c['pairs'], joint_AB=c['joint/combined/AB'],
                     joint_assessable=sum(c['joint/combined/'+s] for s in STATES),
                     full_AB=c['full/combined/AB'], both_indexes_recognized='?' not in b)
              for b,c in sorted(independent.items()) if c['joint/combined/AB'] or c['full/combined/AB']}
    from peanalyzer.workflow import software_identity
    comparison = dict(source=software_identity().model_dump(), inputs=json.loads((HERE/'input-sha256.json').read_text()),
                      oracle_sha256=hashlib.sha256((HERE/'raw_oracle.py').read_bytes()).hexdigest(),
                      cells=dict(cell_counts),by_method=by_method,discrepancies=discrepancies,
                      full_template_to_joint_Q30_1A=retention,observed_AB_bins=raw_ab)
    (out/'independent-comparison.json').write_text(json.dumps(comparison,indent=2,sort_keys=True)+'\n')
    if discrepancies:
        raise ValueError(f'{len(discrepancies)} integer discrepancies; see independent-comparison.json')
    checked=by_method['two_site_q30']['total']+by_method['full_templates']['total']
    with (HERE / 'evidence/site_qc.csv').open() as f:
        for row in csv.DictReader(f):
            b = row.pop('barcode')
            if '?' in b:
                continue
            assert samples[b]['two_site_q30']['combined']['assessable'] == int(row.pop('callable'))
            assert samples[b]['site_exclusions'] == {k:int(v) for k,v in row.items() if int(v)}, b
    assert samples['7G']['status'] == 'EMPTY_NEGATIVE_CONTROL'
    assert samples['7G']['input_pairs'] == 0 and samples['7G']['full_templates']['combined']['assessable'] == 0
    summary = dict(status='passed', barcode_bins=len(samples), raw_pairs=raw['total_input_read_pairs'],
                   assigned_pairs=raw['assigned_expected_pair'], four_state_integer_cells_compared=checked,
                   site_QC_by_barcode='passed', empty_negative_control='7G',
                   marginal_site_integer_cells_compared=4*len(samples),
                   canonical_workflow_WT_PE_cells_compared=2*len(samples), sample_1A=samples['1A'])
    (out / 'candidate-comparison.json').write_text(json.dumps(summary, indent=2, sort_keys=True)+'\n')
    print(f'PASS: {len(samples)} recognized physical indexes and {cell_counts["total"]} integer comparisons ({cell_counts["nonzero"]} nonzero).')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('new_output_directory', type=Path)
    args = parser.parse_args()
    compare(args.inputs, args.new_output_directory)
