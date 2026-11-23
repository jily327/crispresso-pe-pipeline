"""Real two-site workflow, normal entrypoints, empty control and exported lineage."""
import csv
import gzip
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from m7_fixtures import fixture, write_csv
from peanalyzer.backend.synthetic import changed
from openpyxl import load_workbook
from peanalyzer.gui.workspace import WorkspaceStore
from peanalyzer.gui.summary_workbook import FILENAME
from peanalyzer.schemas import reverse_complement
from peanalyzer.workflow import verify_workflow_output

pytestmark = [pytest.mark.crispresso_integration,
              pytest.mark.skipif(os.environ.get('M7_INTEGRATION') != '1', reason='Requires pinned CRISPResso2 2.3.4')]


def prepare(root):
    # The original M7 fixture is synthetic; extend its synthetic RTT and product with one substitution.
    args = fixture(root, samples=2, copies=2, reads=0)
    with args['samples'].open() as f:
        samples = list(csv.DictReader(f))
    for index, sample in enumerate(samples):
        sample['sample_role'] = 'negative_control' if index else 'experimental'
    write_csv(args['samples'], list(samples[0]), samples)
    with args['targets'].open() as f:
        targets = list(csv.DictReader(f))
    molecules = []
    for target in targets:
        wt, a = target['wt_sequence'], target['prime_edited_sequence']
        b = wt[:132] + changed(wt[132]) + wt[133:]
        ab = a[:132] + b[132:]
        target['prime_edited_sequence'] = ab
        target['pegRNA_extension'] = reverse_complement(ab[105:145])
        target['quantification_window_coordinates'] = '122-122_132-132'
        ab_extra = ab[:55] + changed(ab[55]) + ab[56:]
        molecules.extend([wt]*10 + [a]*3 + [b]*4 + [ab]*2 + [ab_extra])
    write_csv(args['targets'], list(targets[0]), targets)
    for mate in (1,2):
        with gzip.open(args[f'r{mate}'], 'wt') as handle:
            for i, seq in enumerate(molecules):
                body = seq[:150] if mate == 1 else reverse_complement(seq[-150:])
                barcode = samples[0]['forward_barcode' if mate == 1 else 'reverse_barcode']
                handle.write(f'@site_fixture_{i}/{mate}\n{barcode}{body}\n+\n{"I" * (len(body)+len(barcode))}\n')
    return args


def run_cli(mode, fixture, output, *extra):
    args = [sys.executable, '-m', 'peanalyzer', mode, '--output', str(output),
            '--crispresso', os.environ.get('M3_CORE_EXECUTABLE','CRISPResso'),
            '--runtime-digest', fixture['runtime_digest'], '--analysis-r1-trim-5p','8', '--analysis-r2-trim-5p','8']
    for key in ('samples','targets','config'):
        args.extend(['--'+key,str(fixture[key])])
    result = subprocess.run([*args, *map(str,extra)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout[-1500:] + result.stderr[-2300:]


def check(output):
    verify_workflow_output(output)
    metric = output/'metrics/bc001/T1'
    raw = json.loads((metric/'intended_sites.json').read_text())
    backend = raw['backend']
    assert backend['input_pairs'] == backend['preprocessed'] == backend['aligned'] == 40
    counts = dict(WT=20, A_only=6, B_only=8, AB=6, other_mixed=0, unassessable=0)
    assert backend['combined']['counts'] == counts
    assert backend['combined']['qc']['AB_full_length_exact'] == 4
    assert backend['combined']['qc']['AB_with_additional_change'] == 2
    assert raw['two_site_q30']['combined']['counts'] == {s:counts[s] for s in ('WT','A_only','B_only','AB')}
    assert raw['full_templates']['combined']['counts']['AB'] == 4
    for copy in ('copy1','copy2'):
        assert raw['full_templates']['copies'][copy]['counts']['AB'] == 2
        assert backend['backend_reference'][copy]['counts']['AB'] == 3
    control = output/'metrics/bc002/T1'
    assert json.loads((control/'sample_qc.json').read_text())['depth_status'] == 'EMPTY_NEGATIVE_CONTROL'
    assert not (control/'core_sites').exists()
    digest = hashlib.sha256((metric/'intended_sites.json').read_bytes()).hexdigest()
    with (metric/'intended_sites.tsv').open() as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    assert any(r['Outcome'] == 'Complete double edit' and r['Numerator']=='6' and r['Denominator']=='40'
               and r['SHA-256'] == digest for r in rows)
    assert digest in (metric/'intended_sites.html').read_text()
    stats = json.loads((output/'statistics/result.json').read_text())
    observed, = [row for row in stats['observations'] if row['sample_id'] == 'bc001'
                 and row['metric_name'] == 'intended_sites.two_site_q30.double_edit' and row['copy_name'] is None]
    assert (observed['numerator'], observed['denominator'], observed['fraction']) == (6, 40, 0.15)
    assert (output/'metrics'/observed['source_result']).resolve() == metric/'intended_sites.json'
    assert {row['sample_id'] for row in stats['provenance']['input_results']} == {'bc001', 'bc002'}
    store = WorkspaceStore([])
    view = store.register_completed('Synthetic sites', output, finalize=True)
    aligned = [p for p in view.scientific_panels if p.method == 'Sites in aligned CRISPResso alleles']
    assert aligned and all(p.source.sha256 == digest for p in aligned)
    workbook = load_workbook(output / FILENAME, read_only=True, data_only=True)
    try:
        measurements = list(workbook['Measurements'].values)
        assert any(row[5:8] == ('Complete double edit', '6', '40') and row[-1] == digest
                   for row in measurements)
    finally:
        workbook.close()
    return dict(counts=counts, source_verified=True, gui_sha256=digest, workbook_verified=True,
                stats_double_edit=[6,40], input_pairs=40, zero_control=True,
                exact_ab=4, backend_version=backend['version'], digest=backend['execution']['runtime_digest'],
                package_code_sha256=json.loads((output/'workflow/plan.json').read_text())['software_identity']['package_code_sha256'])


def test_real_two_site_cli_and_resume(tmp_path):
    root = Path(os.environ.get('INTENDED_SITES_M7_DIR',tmp_path/'study'))
    root.mkdir(parents=True)
    options = prepare(root/'inputs')
    clean, analyze = root/'run',root/'analyze'
    run_cli('run', options, clean, '--r1',options['r1'],'--r2',options['r2'])
    clean_evidence = check(clean)
    before = (clean/'workflow_manifest.json').read_bytes()
    run_cli('run', options, clean, '--r1',options['r1'],'--r2',options['r2'],'--resume')
    assert before == (clean/'workflow_manifest.json').read_bytes()
    run_cli('analyze', options, analyze, '--demux-root',clean/'demux')
    analyze_evidence = check(analyze)
    assert clean_evidence['counts'] == analyze_evidence['counts']
    (root/'evidence.json').write_text(json.dumps(dict(run=clean_evidence,analyze=analyze_evidence,
                                                completed_resume_unchanged=True),indent=2,sort_keys=True)+'\n')
