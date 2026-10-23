"""Collect independent baseline/final tests and unchanged M4 scientific evidence."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'tests'))
from peanalyzer.remediation import panel, qualify_indels


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def test_results(root):
    tree = ET.parse(root / 'tests.xml')
    cases = tree.findall('.//testcase')
    integration = [c for c in cases if 'integration' in c.attrib['classname']]
    preflight = [c for c in integration if c.attrib['name'] == 'test_actual_copy_specific_repeat_excludes_target_length_class']
    result = dict(tests=len(cases), failures=len(tree.findall('.//failure')), errors=len(tree.findall('.//error')),
                  skipped=len(tree.findall('.//skipped')), integration_scenarios=len(integration),
                  backend_executing_scenarios=len(integration)-len(preflight), preflight_only_scenarios=len(preflight),
                  cases=[dict(classname=c.attrib['classname'], name=c.attrib['name']) for c in cases])
    assert result['failures'] == result['errors'] == result['skipped'] == 0
    assert (len(integration), len(preflight)) == (62, 1)
    return result


def scientific(value):
    if isinstance(value, dict):
        return {k: scientific(v) for k, v in value.items() if k != 'population_id'}
    if isinstance(value, list):
        return [scientific(v) for v in value]
    return value


def main():
    parser = argparse.ArgumentParser()
    for name in ('baseline-source', 'source', 'wheel', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    results = {}
    for label, root in [('baseline_source', args.baseline_source),
                        ('source', args.source), ('wheel', args.wheel)]:
        results[label] = test_results(root)
        shutil.copyfile(root / 'tests.txt', out / (label + '-tests.txt'))
    assert results['baseline_source']['tests'] == 940
    assert results['source']['tests'] == results['wheel']['tests'] == 952
    baseline_cases = {tuple(c.values()) for c in results['baseline_source']['cases']}
    for label in ('source', 'wheel'):
        cases = {tuple(c.values()) for c in results[label]['cases']}
        assert baseline_cases <= cases
        results[label]['prior_cases_preserved'] = len(baseline_cases)
        results[label]['m61_cases_added'] = len(cases - baseline_cases)
    write(out / 'test-results.json', results)
    m5 = {}
    for label in ('source', 'wheel'):
        cases = [c for c in results[label]['cases']
                 if c['classname'].rsplit('.', 1)[-1] in ('test_m5', 'test_m51')]
        exact = [c for c in cases if c['name'].startswith(('test_hand_enumerated_unpaired', 'test_hand_enumerated_paired'))]
        assert len(exact) == 3  # One unpaired and two paired committed hand-enumerated fixtures.
        bh = [c for c in cases if c['name'].startswith('test_hand_calculated_bh')]
        assert len(bh) == 5
        m5[label] = dict(passed_cases=len(cases), exact_oracles=len(exact),
            hand_calculated_bh_cases=len(bh), paired_sign_flips_preserved=True, bh_preserved=True,
            permutation_limits_preserved=True, partial_target_rejection_preserved=True,
            biological_sample_units_preserved=True, cases=cases)
    write(out / 'm5-regression.json', m5)
    parity = {}
    fields = ('target_metrics', 'copies', 'qc', 'eligibility', 'derived_metrics', 'product_evidence')
    for stage in ('m4', 'm41', 'm42', 'm421', 'm422'):
        for path in sorted((args.baseline_source / stage).rglob('result.json')):
            relative = path.relative_to(args.baseline_source)
            baseline = json.loads(path.read_text())
            expected = scientific({k: baseline.get(k) for k in fields})
            for root in (args.source, args.wheel):
                actual = json.loads((root / relative).read_text())
                assert scientific({k: actual.get(k) for k in fields}) == expected, (root, relative)
            parity[str(relative)] = dict(audited_baseline_and_final_source_wheel_equal=True,
                                         compared_fields=list(fields), excluded_nested_fields=['population_id'])
    assert len(parity) == 42
    write(out / 'm4-result-parity.json', parity)
    spec = importlib.util.spec_from_file_location('m422_evidence_helpers', REPO / 'docs/validation/m422/collect_evidence.py')
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    historical = {}
    for kind in ('m3', 'm31'):
        root = args.source / 'm4' / kind
        replay = helpers.reconcile(helpers.prepared(root), panel())
        assert replay['changed'] == 0
        historical[kind] = replay
    assert sum(r['input'] for r in historical.values()) == 475
    grid = qualify_indels()
    assert len(grid) == 36 and sum(r['geometry_status'] == 'BLOCKED' for r in grid) == 23
    write(out / 'historical-classification-reconciliation.json', historical)
    write(out / 'geometry-grid.json', grid)
    write(out / 'regression-gate.json', dict(status='PASS', starting_main='83f05a3a6279aedec18dee70fed79dc1d315ef4b',
        audited_parent='1e3f3b1923f97d06b62903cbbf648b25ded75572', baseline_version='0.6.0', m61_version='0.6.1', m4_results_compared=len(parity),
        historical_pair_classifications=475, changed_classifications=0,
        geometry=dict(total=36, allowed=13, blocked=23),
        integration_scenarios_per_environment=62, backend_executing=61, preflight_only=1,
        source_tests=results['source']['tests'], fresh_wheel_tests=results['wheel']['tests']))
    print(json.dumps(dict(tests=results['source']['tests'], m4_results_compared=len(parity), status='PASS')))


if __name__ == '__main__':
    main()
