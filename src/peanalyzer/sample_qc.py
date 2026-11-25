"""Sample-level depth and explicitly declared empty-control evidence."""
from typing import Literal

from pydantic import Field, JsonValue, model_validator

from peanalyzer.nuclease.targets import NucleaseTarget
from peanalyzer.schemas import Identifier
from peanalyzer.statistical_models import Hash, Model


def depth_assessment(sample_id, role, prepared_pairs, minimum, result):
    """Advisory depth after each metric's own authoritative denominator selection."""
    records = []
    def record(name, copy, status, denominator, policy_id=None):
        qc = 'NOT_ASSESSABLE' if denominator is None else ('MEETS_MINIMUM' if denominator >= minimum else 'BELOW_MINIMUM')
        records.append(dict(metric_name=name, copy_name=copy, policy_id=policy_id, measurement_status=status,
                            measured_denominator=denominator, qc_status=qc))

    if getattr(result, 'analysis_mode', 'precise_edit') == 'precise_edit':
        for metric in [*dict(result.target_metrics).values(),
                       *(r for group in result.copies.values() for r in (group.precise, group.native))]:
            record(metric.metric_name, metric.copy_id, metric.status, metric.denominator)
        for group in result.derived_metrics.values():
            for metric in group.values():
                record(metric.metric_name, metric.copy_id, metric.status, metric.denominator, metric.policy_id)
    else:
        from peanalyzer.nuclease.models import observation_populations
        for copy, group in observation_populations(result).items():
            for name, metric in group.metrics.items():
                denominator = metric.denominator if group.status == 'REPORTABLE' else None
                record(name, copy, group.status, denominator)
    return dict(schema_version=1, sample_id=sample_id, sample_role=role,
                prepared_read_pairs=prepared_pairs, minimum_prepared_read_pairs=minimum,
                depth_status=('EMPTY_NEGATIVE_CONTROL' if role == 'negative_control' else 'EMPTY_EXPERIMENTAL_SAMPLE')
                if prepared_pairs == 0 else ('BELOW_MINIMUM' if prepared_pairs < minimum else 'MEETS_MINIMUM'),
                threshold_scope='prepared_read_pairs', threshold_action='flag_for_review', metric_depth=records)


class EmptyProvenance(Model):
    target_definitions_sha256: Hash
    prepared_manifest_sha256: Hash
    prepared_sample: dict[str, JsonValue]


class EmptyNucleaseControl(Model):
    schema_version: Literal[1] = 1
    metric_contract_version: Literal['empty-nuclease-control-v1'] = 'empty-nuclease-control-v1'
    analysis_mode: Literal['indel_nuclease'] = 'indel_nuclease'
    sample_role: Literal['negative_control'] = 'negative_control'
    sample_id: Identifier
    target_id: Identifier
    analysis_id: str = Field(min_length=1)
    targets: list[NucleaseTarget] = Field(min_length=1)
    status: Literal['NOT_ASSESSABLE'] = 'NOT_ASSESSABLE'
    reason_codes: list[Literal['EMPTY_NEGATIVE_CONTROL']] = Field(min_length=1, max_length=1)
    backend_status: Literal['not_invoked'] = 'not_invoked'
    provenance: EmptyProvenance

    @model_validator(mode='after')
    def reconcile(self):
        from peanalyzer.metrics.production import digest
        sample = self.provenance.prepared_sample
        if type(sample.get('pairs')) is not int or sample['pairs'] != 0:
            raise ValueError('empty control requires zero prepared pairs')
        if set(sample.get('files', {})) != {'r1', 'r2'}:
            raise ValueError('missing empty paired-end input inventory')
        if (any(t.target_name != self.target_id for t in self.targets)
                or len({t.copy_name for t in self.targets}) != len(self.targets)
                or digest([t.model_dump() for t in self.targets]) != self.provenance.target_definitions_sha256):
            raise ValueError('empty control target inventory mismatch')
        return self

    @property
    def metrics(self):
        from peanalyzer.nuclease.models import METRICS
        return dict.fromkeys(METRICS)


def validate_qc(plan, node, result, output):
    from pathlib import Path
    from peanalyzer.workflow_storage import WorkflowError, read_json
    manifest = read_json(Path(plan.output) / 'analysis/analysis_manifest.json')
    sample = manifest['samples'][node.sample_id]
    role = next(s.get('sample_role', 'experimental') for s in plan.samples if s['barcode_id'] == node.sample_id)
    expected = depth_assessment(node.sample_id, role, sample['pairs'], plan.normalized_options['min_prepared_pairs_qc'], result)
    if read_json(output / 'sample_qc.json') != expected:
        raise WorkflowError('SAMPLE_DEPTH_QC_MISMATCH', node.stage_id)
    if expected['depth_status'] == 'EMPTY_NEGATIVE_CONTROL':
        from peanalyzer.demux_verify import sha256_file
        if (result.provenance.prepared_manifest_sha256 != sha256_file(Path(plan.output) / 'analysis/analysis_manifest.json')
                or result.provenance.prepared_sample != sample):
            raise WorkflowError('EMPTY_CONTROL_LINEAGE_MISMATCH', node.stage_id)


def write_empty_control(verified, output, *, sample_id, analysis_id, targets,
                        analysis_root, runtime_digest, routing_root=None, tolerance_policies=None):
    from peanalyzer.metrics.production import collect_metrics, digest
    from peanalyzer.metrics.family import reaggregate
    from peanalyzer.workflow_storage import atomic_json

    sample = verified.manifest['samples'][sample_id]
    if sample['pairs'] != 0:
        raise ValueError('cannot skip backend for a populated control')
    output.mkdir()
    if targets[0].analysis_mode == 'indel_nuclease':
        result = EmptyNucleaseControl(sample_id=sample_id, target_id=targets[0].target_name,
            analysis_id=analysis_id, targets=targets, reason_codes=['EMPTY_NEGATIVE_CONTROL'],
            provenance=EmptyProvenance(target_definitions_sha256=digest([t.model_dump() for t in targets]),
                prepared_manifest_sha256=verified.manifest_sha256, prepared_sample=sample))
    else:
        result = collect_metrics(analysis_root=analysis_root, sample_id=sample_id, targets=targets,
            analysis_id=analysis_id, comparator_root=output/'comparator', routing_root=routing_root,
            runtime_digest=runtime_digest, empty_negative_control=True)
        if tolerance_policies:
            result.derived_metrics = {key: reaggregate(evidence, tolerance_policies)
                                      for key, evidence in result.product_evidence.items()}
    atomic_json(output/'result.json', result.model_dump(mode='json'))
    atomic_json(output/'execution_failures.json', {})
