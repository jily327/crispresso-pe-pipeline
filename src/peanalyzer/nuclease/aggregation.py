"""Adapt validated nuclease sample counts to the existing biological-sample engine."""
import csv
import io
import os
import platform
from pathlib import Path
from peanalyzer import __version__
from peanalyzer.aggregation import (AggregationError,strict_json,sha256,canonical,condition_key,series_key,
    subset)
from peanalyzer import aggregation
from peanalyzer.schemas import BIOLOGICAL_ROLE_POLICY, Sample, biological_role, pcr_control_role
from peanalyzer.validation import SAMPLE_COLUMNS,_load_csv
from peanalyzer.statistical_models import BiologicalSample,InputResult
from peanalyzer.metrics.production import digest
from peanalyzer.nuclease.models import NucleaseMetricResult,NucleaseObservation,NucleaseStatisticsProvenance,NucleaseStatisticsResult


def is_nuclease_manifest(path):
    path=Path(path)
    with path.open(newline='',encoding='utf-8-sig') as handle:
        rows=list(csv.reader(handle,strict=True))
    if not rows or rows[0]!=['result_json']:raise AggregationError('manifest must have exactly one column: result_json')
    if len(rows)<2 or any(len(r)!=1 or not r[0].strip() for r in rows[1:]):raise AggregationError('invalid result manifest')
    values=[strict_json((path.parent/r[0].strip()).read_bytes()) for r in rows[1:]]
    if any(not isinstance(v,dict) for v in values):raise AggregationError('scientific result must be a JSON object')
    kinds={v.get('metric_contract_version') for v in values}
    nuclease={'indel-nuclease-v1','empty-nuclease-control-v1','indel-nuclease-multicopy-v1'}
    if kinds & nuclease:
        if kinds - nuclease:raise AggregationError('MIXED_ANALYSIS_MODES_UNSUPPORTED')
        return True
    return False


def collect(manifest_path,samples_path):
    manifest_path,samples_path=Path(manifest_path).resolve(),Path(samples_path).resolve()
    raw_manifest,raw_samples=manifest_path.read_bytes(),samples_path.read_bytes()
    rows=list(csv.reader(io.StringIO(raw_manifest.decode('utf-8-sig')),strict=True))
    if not rows or rows[0]!=['result_json'] or len(rows)<2 or any(len(r)!=1 or not r[0].strip() for r in rows[1:]):raise AggregationError('invalid manifest')
    paths=[(manifest_path.parent/r[0].strip()).resolve() for r in rows[1:]]
    if len(paths)!=len(set(paths)):raise AggregationError('duplicate resolved result path')
    samples=_load_csv(samples_path,Sample,tuple(c for c in SAMPLE_COLUMNS if c not in {'forward_barcode','reverse_barcode'}))
    for field in ('sample_name','barcode_id'):
        if len({getattr(s,field) for s in samples})!=len(samples):raise AggregationError('duplicate sample identity')
    metadata={s.barcode_id:s for s in samples}
    observed=[];inputs=[];results=[];seen=set();replicates=set();definitions={}
    snapshots={manifest_path:sha256(raw_manifest),samples_path:sha256(raw_samples)}
    for path in sorted(paths):
        data=path.read_bytes();snapshots[path]=sha256(data)
        from peanalyzer.result_dispatch import metric_model
        raw=strict_json(data); result=metric_model(raw).model_validate(raw);results.append(result)
        if result.sample_id not in metadata:raise AggregationError('sample absent from metadata barcode_id')
        sample=metadata[result.sample_id]
        if result.metric_contract_version=='empty-nuclease-control-v1' and (not pcr_control_role(sample.sample_role) or result.sample_role != sample.sample_role):
            raise AggregationError('empty control role differs from sample metadata')
        key=(result.sample_id,result.target_id)
        if key in seen:raise AggregationError('duplicate analysis for sample x target')
        seen.add(key);rep=(condition_key(sample),result.target_id,sample.biological_replicate)
        if biological_role(sample.sample_role):
            if rep in replicates:raise AggregationError('duplicate biological_replicate within condition and target')
            replicates.add(rep)
        definition=result.provenance.target_definitions_sha256
        if definitions.setdefault(result.target_id,definition)!=definition:raise AggregationError('conflicting target identity across analyses')
        source=Path(os.path.relpath(path,manifest_path.parent)).as_posix()
        inputs.append(InputResult(source_result=source,sha256=snapshots[path],sample_id=result.sample_id,target_name=result.target_id,analysis_id=result.analysis_id))
        from peanalyzer.nuclease.models import observation_populations
        populations = observation_populations(result)
        for copy, group in populations.items():
            scope = 'confident_copy' if copy is not None else 'target_all_prepared'
            identity = dict(prepared=result.provenance.prepared_manifest_sha256, sample=result.sample_id,
                            target=definition, scope='single_copy_identity')
            if len(populations) > 1:
                identity.update(scope=scope, copy_name=copy, method='conservative_flanking_markers_v1')
            for name,metric in group.metrics.items():
                reportable = group.status == 'REPORTABLE'
                observed.append(NucleaseObservation(**subset(sample,BiologicalSample).model_dump(),sample_id=result.sample_id,
                    target_name=result.target_id,metric_name=name,population_scope=scope,routing_conditioned=copy is not None,
                    copy_name=copy,policy_id=None,policy_definition=None, population_id=digest(identity),status=group.status,
                    numerator=metric.numerator if reportable else None, denominator=metric.denominator if reportable else None,
                    fraction=metric.fraction if reportable else None,reason_codes=group.reason_codes,
                    analysis_id=result.analysis_id,metric_contract_version=result.metric_contract_version,source_result=source))
    if seen!={(s,t) for s,_ in seen for t in definitions}:raise AggregationError('PARTIAL_SAMPLE_TARGET_COVERAGE')
    for path,checksum in snapshots.items():
        if sha256(path.read_bytes())!=checksum:raise AggregationError('input changed during collection')
    observed.sort(key=lambda r:(series_key(r),condition_key(r),r.sample_name))
    return NucleaseStatisticsResult(schema_version=1,statistics_contract_version='indel-nuclease-stats-v1',
        provenance=NucleaseStatisticsProvenance(package_version=__version__,source_metric_contract_versions=sorted({r.metric_contract_version for r in results}),
            input_results=sorted(inputs,key=lambda r:(r.sample_id,r.target_name)),samples_path=str(samples_path),manifest_path=str(manifest_path),
            contrast_specification_path=None,contrast_specification_hash=None,
            invocation_parameters=dict(command='summarize',biological_role_policy=BIOLOGICAL_ROLE_POLICY,sample_identity_column='barcode_id',result_paths_relative_to='manifest_directory',
                analysis_mode='indel_nuclease',primary_outcome='indel_fraction'),python=platform.python_version(),platform=platform.platform()),
        input_manifest_hash=sha256(raw_manifest),sample_metadata_hash=sha256(raw_samples),observations=observed,
        group_summaries=aggregation.summarize_groups(observed),contrasts=[],multiple_testing_families=[],
        nuclease_results=sorted(results,key=lambda r:(r.sample_id,r.target_id)),
        unused_metadata_sample_ids=sorted(s.sample_name for s in samples if s.barcode_id not in {x for x,_ in seen}))
