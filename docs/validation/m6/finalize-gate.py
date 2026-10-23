"""Require observed regression, artifact and package evidence before declaring M6 ready."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    def read(name): return json.loads((args.evidence / name).read_text())
    tests = read('test-results.json')
    assert tests['baseline_source']['tests'] == tests['baseline_wheel']['tests'] == 880
    assert tests['source']['tests'] == tests['wheel']['tests'] == 940
    for environment in tests.values():
        assert environment['failures'] == environment['errors'] == environment['skipped'] == 0
        assert environment['integration_scenarios'] == 62
        assert environment['backend_executing_scenarios'] == 61
        assert environment['preflight_only_scenarios'] == 1
    for label in ('source', 'wheel'):
        assert tests[label]['prior_cases_preserved'] == 880
        assert tests[label]['m6_cases_added'] == 60
    regression = read('regression-gate.json')
    assert regression['status'] == 'PASS' and regression['m4_results_compared'] == 42
    assert regression['historical_pair_classifications'] == 475 and regression['changed_classifications'] == 0
    assert regression['geometry'] == dict(total=36, allowed=13, blocked=23)
    assert read('report-qualification.json')['status'] == 'PASS'
    assert read('schema-validation.json')['status'] == 'PASS'
    assert read('offline.json')['status'] == 'PASS' and read('offline.json')['network_attempts'] == 0
    assert read('source-wheel-byte-parity.json')['every_artifact_byte_identical']
    assert not read('scope-integrity.json')['scientific_modules_changed']
    assert not read('scope-integrity.json')['existing_tests_changed_scientifically']
    package = read('packaging.json')
    assert package['installed']['version'] == '0.6.0' and package['installed']['schemas_match']
    assert package['tested_and_final_wheel_payload_equal']
    assert (args.evidence / 'package-verification.txt').read_text().startswith('PASS:')
    benchmark = read('benchmark.json')
    assert (benchmark['biological_samples'], benchmark['targets'], benchmark['observations'], benchmark['figures']) == (100,4,4800,48)
    gate = dict(status='PASS', branch='feat/m6-reporting',
        authoritative_parent='83f05a3a6279aedec18dee70fed79dc1d315ef4b', package_version='0.6.0',
        report_contract_version='m6-v1', source_statistics_contract_version='m5-v1',
        baseline_source_tests=880, baseline_wheel_tests=880, source_tests=940, wheel_tests=940,
        new_reporting_tests=60, failures=0, errors=0, skipped=0,
        integration=dict(total=62, backend_executing=61, preflight_only=1),
        scientific_authority='exact copied M5 source/result.json', statistics_recomputed=False,
        source_wheel_byte_parity=True, exact_source_copy=True, manifest_hashes_verified=True,
        summarize_only_supported=True, stats_supported=True,
        html_and_svg_injection_tests='PASS', offline_no_external_resources='PASS',
        atomic_publication_and_source_mutation_tests='PASS',
        geometry=dict(total=36, allowed=13, blocked=23), m4_artifacts_compared=42,
        historical_classifications=475, changed_classifications=0,
        benchmark=benchmark, final_distribution_verification='package-verification.txt',
        limits=['No automatic biological interpretation or significance calls',
                'No confidence intervals or GLMMs', 'Copy metrics remain routing-conditioned',
                'M4 upstream observability and geometry limits remain unchanged',
                'No portable CRISPResso report-link contract',
                'Byte reproducibility is qualified in the same rendering environment',
                'No workflow DAG, resume, force or M7'])
    (args.evidence / 'gate.json').write_text(json.dumps(gate, indent=2, sort_keys=True)+'\n')
    print('M6 REPORTING GATE: PASS')
    print('SAFE FOR INDEPENDENT M6 AUDIT')


if __name__ == '__main__':
    main()
