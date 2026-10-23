"""Build fully synthetic M5 presentation fixtures; never executes a backend."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tests'))
from m5_fixtures import dataset
from peanalyzer.aggregation import summarize_groups
from peanalyzer.statistics import stats
from peanalyzer.statistical_models import StatisticsResult


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def create(paired):
    with tempfile.TemporaryDirectory() as directory:
        options = dataset(Path(directory), paired=paired)
        for path in Path(directory).glob('*-T*.json'):
            value = json.loads(path.read_text())
            sample = value['sample_id'].split('-')[1]
            tenth = int(sample[-1]) + (0 if sample[0] == 'A' else 5)
            from m5_fixtures import result_document
            write(path, result_document(value['sample_id'], value['target_id'], tenth, 10))
        result = stats(**options)
    data = result.model_dump(mode='json')
    data['provenance'].update(package_version='0.5.1', samples_path='synthetic/samples.csv',
        manifest_path='synthetic/metrics_manifest.csv', contrast_specification_path='synthetic/contrasts.yaml',
        python='synthetic', platform='synthetic', input_results=[])
    data['input_manifest_hash'] = '0'*64
    data['sample_metadata_hash'] = '1'*64
    data['provenance']['contrast_specification_hash'] = '2'*64
    for observation in data['observations']:
        observation['source_result'] = 'synthetic/' + observation['sample_id'] + '-' + observation['target_name'] + '.json'
        if observation['target_name'] == 'T2' and observation['metric_name'] == 'total_pe_family' and observation['policy_id'] == 'policy1':
            if observation['sample_name'] in ('A001', 'A002'):
                status = 'BLOCKED' if observation['sample_name'] == 'A001' else 'NOT_ASSESSABLE'
                observation.update(status=status, numerator=None, denominator=None, fraction=None, reason_codes=['SYNTHETIC_' + status])
    data['observations'] = [o for o in data['observations'] if not (o['sample_name'] == 'A003' and o['target_name'] == 'T2'
        and o['metric_name'] == 'total_pe_family' and o['policy_id'] == 'policy1')]
    from peanalyzer.statistical_models import Observation
    data['group_summaries'] = [g.model_dump(mode='json') for g in summarize_groups([Observation.model_validate(o) for o in data['observations']])]
    for contrast in data['contrasts']:
        if not paired and contrast['contrast_id'] == 'native':
            contrast.update(difference_in_biological_sample_fraction=.5, p_value=.1, q_value=.2, permutation_space_size=20, permutation_count=20, extreme_count=2)
        if contrast['contrast_id'] in ('copy', 'family'):
            contrast.update(status='BLOCKED' if contrast['contrast_id'] == 'copy' else 'NOT_ASSESSABLE',
                reason_codes=['SYNTHETIC_PRESENTATION_STATE'], difference_in_biological_sample_fraction=None,
                p_value=None, q_value=None, permutation_count=None, extreme_count=None)
        if paired:
            contrast['excluded_blocks'] = [dict(block_id='synthetic-excluded-block', group_a_sample_ids=[], group_b_sample_ids=[], reason_codes=['SYNTHETIC_EXCLUDED_BLOCK'])]
    for family in data['multiple_testing_families']:
        valid = sorted(c['contrast_id'] for c in data['contrasts'] if c['family_id'] == family['family_id'] and c['status'] == 'REPORTABLE')
        family.update(valid_contrast_ids=valid, valid_test_count=len(valid))
        for contrast in data['contrasts']:
            if contrast['family_id'] == family['family_id']: contrast['valid_tests_in_family'] = len(valid)
    return StatisticsResult.model_validate(data).model_dump(mode='json')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for name, paired in [('unpaired', False), ('paired', True)]:
        write(args.output / (name + '.json'), create(paired))
    identity = dict(target_name='T1', metric_name='target_crispresso_native_pe', population_scope='target_all_prepared',
                    routing_conditioned=False, copy_name=None, policy_id=None, policy_definition=None)
    encoded = json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()
    write(args.output / 'oracle.json', dict(native_figure_id='series-' + hashlib.sha256(encoded).hexdigest() + '-samples',
        sample_fractions=[.1,.2,.3,.6,.7,.8], stored_means=[.2,.7], sample_figures=24, contrast_figures=2,
        artifacts=31, contrast=dict(difference_in_biological_sample_fraction=.5, p_value=.1, q_value=.2),
        reportability_T2_policy1_A=dict(expected=3, reportable=0, blocked=1, not_assessable=1, missing=1)))


if __name__ == '__main__':
    main()
