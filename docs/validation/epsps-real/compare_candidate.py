"""Exercise the installed candidate CLI, independent of the frozen v1.0.1 reader."""
import argparse
import csv
from collections import Counter
from types import SimpleNamespace
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile

from audit import HERE, STATES, calls, validate_sources


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
    from verify_marginal import count_marginal, site_oracle
    patterns = site_oracle(refs['chr01g']['wt_sequence'], 146, 157)
    for sample in verify_demux_output(archive).samples:
        measures = samples[sample.sample_id]['two_site_q30']['combined']
        assert count_marginal(sample, patterns) == [(measures[key]['numerator'], measures[key]['denominator'])
                                                    for key in ('site_A', 'site_B')], sample.sample_id
        canonical = Counter()
        for records in paired_fastq(sample.r1, sample.r2):
            if len(records[0].sequence) > 26 and len(records[1].sequence) > 27:
                prepared = tuple(rec.trimmed(n) for rec, n in zip(records, (26, 27)))
                canonical[assess_pair(prepared, targets)['canonical']] += 1
        expected_counts = samples[sample.sample_id]['full_templates']['combined']['counts']
        assert [canonical['exact_WT'], canonical['exact_PE']] == [expected_counts['WT'], expected_counts['AB']], sample.sample_id
    checked = 0
    with (HERE / 'evidence/haplotypes.csv').open() as f:
        for row in csv.DictReader(f):
            b = row['barcode']
            if '?' in b:
                continue
            name = 'two_site_q30' if row['method'] == 'both_mates_Q30_sites' else 'full_templates'
            group = samples[b][name]
            c = row['copy']
            result = group['combined'] if c == 'combined' else group['unresolved_copy'] if c == 'unresolved' else group['copies'][c]
            assert result['counts'] == {s: int(row[s]) for s in STATES}, (b, name, c, result, row)
            assert result['assessable'] == int(row['four_state_denominator'])
            checked += len(STATES)
    with (HERE / 'evidence/site_qc.csv').open() as f:
        for row in csv.DictReader(f):
            b = row.pop('barcode')
            if '?' in b:
                continue
            assert samples[b]['two_site_q30']['combined']['assessable'] == int(row.pop('callable'))
            assert samples[b]['site_exclusions'] == {k:int(v) for k,v in row.items() if int(v)}, b
    assert samples['7G']['status'] == 'EMPTY_NEGATIVE_CONTROL'
    assert samples['7G']['exact_double_edit_fraction']['fraction'] is None
    summary = dict(status='passed', barcode_bins=len(samples), raw_pairs=raw['total_input_read_pairs'],
                   assigned_pairs=raw['assigned_expected_pair'], four_state_integer_cells_compared=checked,
                   site_QC_by_barcode='passed', empty_negative_control='7G',
                   marginal_site_integer_cells_compared=4*len(samples),
                   canonical_workflow_WT_PE_cells_compared=2*len(samples), sample_1A=samples['1A'])
    (out / 'candidate-comparison.json').write_text(json.dumps(summary, indent=2, sort_keys=True)+'\n')
    print(f'PASS: {len(samples)} physical indexes and {checked} integer count comparisons')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('new_output_directory', type=Path)
    args = parser.parse_args()
    compare(args.inputs, args.new_output_directory)
