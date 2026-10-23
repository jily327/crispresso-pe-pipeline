"""Independent JSON Schema qualification; jsonschema is an audit-only tool."""
import argparse
import copy
from importlib.metadata import version
import json
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--schema', type=Path, required=True)
    parser.add_argument('--reports', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    schema = json.loads(args.schema.read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    manifests = sorted(args.reports.glob('*/report_manifest.json'))
    assert len(manifests) == 2
    for path in manifests:
        validator.validate(json.loads(path.read_text()))
    original = json.loads(manifests[0].read_text())
    rejected = []
    for case in ('unknown_field', 'wrong_contract', 'boolean_version', 'hash_pattern', 'media_type', 'missing_required'):
        value = copy.deepcopy(original)
        if case == 'unknown_field': value['extra'] = 'unexpected'
        elif case == 'wrong_contract': value['report_contract_version'] = 'm6-v2'
        elif case == 'boolean_version': value['schema_version'] = True
        elif case == 'hash_pattern': value['source_result_sha256'] = 'wrong'
        elif case == 'media_type': value['artifacts'][0]['media_type'] = 'invalid'
        elif case == 'missing_required': del value['title']
        try:
            validator.validate(value)
        except ValidationError:
            rejected.append(case)
        else:
            raise AssertionError(case)
    result = dict(status='PASS', validator='jsonschema', validator_version=version('jsonschema'),
        schema_draft='2020-12', valid_manifests=len(manifests), rejected_mutations=rejected,
        dependency_role='independent audit tool; not a package runtime dependency',
        cross_field_checks='Pydantic and runtime artifact/hash verification')
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print('PASS: independent JSON Schema validation and six invalid-manifest attacks')


if __name__ == '__main__':
    main()
