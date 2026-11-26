"""The M4 precise-edit record owns canonical whole-product eligibility."""
import json

CONTRACT = 'm4-total-precise-pe-v1'


def canonical_site_metric(record):
    n, d = record.numerator, record.denominator
    return dict(numerator=n, denominator=d, fraction=n / d if d is not None else None,
                status=record.status, reason_codes=list(record.reason_codes),
                population_id=record.population_id, metric_name=record.metric_name)


def verify_canonical_binding(raw, record, *, required=False):
    contract = raw.get('canonical_eligibility_contract')
    if contract is None and not required:
        return
    expected = canonical_site_metric(record)
    if (contract != CONTRACT or json.dumps(raw.get('exact_double_edit_fraction'), sort_keys=True) !=
            json.dumps(expected, sort_keys=True)):
        raise ValueError('Canonical two-site value or eligibility differs from target_metrics.total_precise_pe')
