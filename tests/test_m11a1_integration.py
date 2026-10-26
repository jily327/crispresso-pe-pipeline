"""Real execution oracle for the setup-only ambiguous-placement warning."""
import csv
import gzip
import json
import os
from pathlib import Path

import pytest
from m7_fixtures import fixture, write_csv
from peanalyzer.remediation import indel_designs
from peanalyzer.schemas import reverse_complement
from peanalyzer.workflow import execute_workflow, verify_workflow_output

pytestmark = [pytest.mark.crispresso_integration,
    pytest.mark.skipif(os.environ.get('M11A1_INTEGRATION') != '1', reason='requires qualified Core 2.3.4')]


def test_ambiguous_deletion_execution_retains_target_precise_metric(tmp_path):
    root = Path(os.environ.get('M11A1_RESULTS_DIR', tmp_path/'m11a1'))
    options = fixture(root/'inputs', samples=1)
    targets = next(ts for d, ts in indel_designs() if d['id'] == 'deletion_1_seed11')
    rows = [t.model_dump() for t in targets]
    write_csv(options['targets'], list(rows[0]), rows)
    sample = next(csv.DictReader(options['samples'].open()))
    for mate in (1, 2):
        with gzip.open(options[f'r{mate}'], 'wt') as handle:
            for target in targets:
                for i in range(12):
                    seq = target.wt_sequence if i < 6 else target.prime_edited_sequence
                    read = seq[:150] if mate == 1 else reverse_complement(seq[-150:])
                    read = sample['forward_barcode' if mate == 1 else 'reverse_barcode'] + read
                    handle.write(f'@{target.copy_name}_{i}/{mate}\n{read}\n+\n'+ 'I'*len(read)+'\n')
    options.update(output=root/'workflow', crispresso=os.environ.get('M3_CORE_EXECUTABLE', 'CRISPResso'))
    execute_workflow(**options)
    assert verify_workflow_output(options['output']).status == 'COMPLETED'
    result = json.loads((options['output']/'metrics/bc001/SYN/result.json').read_text())
    precise = result['target_metrics']['total_precise_pe']
    assert precise['status'] == 'REPORTABLE'
    assert (precise['numerator'], precise['denominator']) == (12, 24)
    assert result['eligibility']['routing_geometry_status'] == 'BLOCKED'
    assert all(c['precise']['status'] == 'BLOCKED' for c in result['copies'].values())
    (root/'execution-oracle.json').write_text(json.dumps(dict(
        fixture='deletion_1_seed11', target_precise=precise,
        eligibility=result['eligibility'],
        copy_statuses={k:v['precise']['status'] for k,v in result['copies'].items()}), indent=2)+'\n')
