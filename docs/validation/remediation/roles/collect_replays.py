"""Check the four standalone SCI-04 runs and archive the synthetic reproduction inputs.

python collect_replays.py CORRECTED_WORKSPACE DIRECT_ROOT NEW_ZIP OUTPUT_JSON
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def indels(archive):
    with ZipFile(archive) as z, z.open('Alleles_frequency_table.txt') as raw:
        rows = list(csv.DictReader(io.TextIOWrapper(raw), delimiter='\t'))
    assert {row['Reference_Name'] for row in rows} == {'Reference'}
    return (sum(int(row['#Reads']) for row in rows if int(row['n_deleted']) or int(row['n_inserted'])),
            sum(int(row['#Reads']) for row in rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('workspace', 'direct_root', 'archive', 'json'):
        parser.add_argument(arg, type=Path)
    args = parser.parse_args()
    truth = {'bc001': (1, 10), 'bc002': (90, 100), 'bc003': (2, 10), 'bc004': (3, 10)}
    assert {p.parent.name for p in args.direct_root.glob('*/parity.json')} == truth.keys()
    summary = {}
    files = {}
    for sample, counts in truth.items():
        cell = args.workspace/'metrics'/sample/'T1'
        manifest = json.loads((cell/'native_runs.json').read_bytes())
        (run,) = manifest['runs']
        direct = args.direct_root/sample
        receipt = json.loads((direct/'parity.json').read_bytes())
        assert run['id'] == receipt['id'] == 'single_reference' and receipt['sample'] == sample
        assert receipt['status'] == 'PASS' and receipt['runtime_match'] and receipt['count_parity']
        assert receipt['alleles_equal'] and receipt['effective_arguments_equal']
        assert receipt['reference_order_sequences_and_windows_equal']
        assert all(r['direct'] == r['managed'] and r['difference'] == 0 for r in receipt['integers'])
        assert receipt['input_sha256'] == [sha(cell/run['paths'][k]) for k in ('r1','r2')]
        assert receipt['script_sha256'] == sha(cell/run['paths']['script'])
        assert receipt['managed_info_sha256'] == sha(cell/run['paths']['info'])
        direct_output = direct/'replay/output/CRISPResso_on_nuclease'
        assert receipt['direct_info_sha256'] == sha(direct_output/'CRISPResso2_info.json')
        assert indels(cell/run['paths']['alleles']) == indels(direct_output/'Alleles_frequency_table.zip') == counts
        summary[sample] = dict(status=receipt['status'], integer_fields=len(receipt['integers']),
                               indel=counts[0], aligned=counts[1], parity_receipt_sha256=sha(direct/'parity.json'))
        # Preserve the complete managed report, including all assets used by its HTML page.
        for path in sorted(cell.rglob('*')):
            if path.is_file():
                files[f'{sample}/{path.relative_to(cell)}'] = path
        files[f'{sample}/direct/parity.json'] = direct/'parity.json'
        for name in ('CRISPResso2_info.json', 'Alleles_frequency_table.zip',
                     'CRISPResso_mapping_statistics.txt', 'CRISPResso_quantification_of_editing_frequency.txt'):
            files[f'{sample}/direct/{name}'] = direct_output/name
    for name in ('PEAnalyzer_Summary.xlsx', 'statistics/control_and_technical_qc.tsv',
                 'statistics/result.json', 'workflow/plan.json', 'workflow_manifest.json'):
        files[name] = args.workspace/name
    with ZipFile(args.archive, 'x', compression=ZIP_DEFLATED) as archive:
        for name, path in sorted(files.items()):
            archive.write(path, name)
    args.json.write_text(json.dumps(dict(samples=summary, archive_sha256=sha(args.archive),
                                         archive_members=len(files)), indent=2, sort_keys=True)+'\n')


if __name__ == '__main__':
    main()
