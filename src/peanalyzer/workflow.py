"""Local serial M7 orchestration; all scientific work belongs to existing APIs."""
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import io
import os
from pathlib import Path
import shutil
import uuid

import yaml

from peanalyzer.analysis_fastq import PreparationConfig, prepare_analysis_fastqs
from peanalyzer.analysis_verify import verify_analysis_output
from peanalyzer.aggregation import summarize
from peanalyzer.backend.core import verify_routing_output
from peanalyzer.backend.pooled import resolve_executable
from peanalyzer.barcodes import Catalog, bundled_catalog, load_catalog
from peanalyzer.demux import demultiplex
from peanalyzer.demux_verify import verify_demux_output
from peanalyzer.geometry import geometry
from peanalyzer.metrics import MetricResult, run_metrics
from peanalyzer.nuclease.backend import run_nuclease_metrics
from peanalyzer.result_dispatch import metric_model, statistics_model, report_model
from peanalyzer.provenance import software_provenance
from peanalyzer.reporting import generate_report
from peanalyzer.reporting_models import DEFAULT_TITLE, ReportManifest
from peanalyzer.routing import RoutingPolicy, policy_identity, route_analysis
from peanalyzer.statistical_models import StatisticsResult
from peanalyzer.statistics import stats
from peanalyzer.validation import UniqueKeyLoader, load_config, load_samples, load_targets
from peanalyzer.workflow_models import (Backend, Dependency, InputArtifact, Plan, Session,
    Software, StageManifest, WorkflowManifest, dag)
from peanalyzer.workflow_storage import (WorkflowError, artifact, atomic_json, canonical,
    digest, inventory, load, no_symlinks, owned, read_json, sha, verify_artifact)

FORCE_FAMILIES = ('demux', 'analysis', 'routing', 'metrics', 'statistics', 'report', 'all')
API = dict(raw_inputs='hash_input_files', external_demux='verify_demux_output', demux='demultiplex',
    analysis='prepare_analysis_fastqs', routing='route_analysis', metrics='run_metrics',
    metrics_manifest='write_metrics_manifest', statistics='summarize|stats', report='generate_report')
LIMITATIONS = [
    'Production execution supports one biological target only; multi-target DAG planning is supported, but target-specific read selection is not defined.',
    'Local serial execution only; no scheduler, distributed execution or automatic biological interpretation.',
    'Exclusive lock files require manual ownership review after a hard kill; no automatic stale-lock stealing.',
    'Workspace relocation is unsupported: existing stage contracts retain absolute lineage paths.',
    'Local hashes detect accidental corruption, not coordinated malicious rewriting of all provenance.',
    'M4/M5/M6 scientific and presentation limits remain unchanged; no portable CRISPResso HTML links.']


def utc():
    return datetime.now(timezone.utc).isoformat()


def software_identity():
    value = software_provenance()
    value.pop('python_executable')
    package = Path(__file__).parent
    value['package_code_sha256'] = digest({p.relative_to(package).as_posix(): sha(p)
        for p in sorted(package.rglob('*')) if p.is_file() and p.suffix in ('.py', '.json', '.yaml', '.csv', '.css')})
    return Software.model_validate(value)


def input_record(path, role, *, snapshot=True):
    path = no_symlinks(path).resolve(strict=True)
    if not path.is_file():
        raise WorkflowError('INVALID_INPUT', str(path))
    checksum = sha(path)
    return InputArtifact(source_path=str(path), sha256=checksum, size_bytes=path.stat().st_size,
        snapshot=f'inputs/{checksum}/{role}{path.suffix}' if snapshot else None)


def verify_inputs(inputs):
    for role, item in inputs.items():
        path = no_symlinks(item.source_path)
        if not path.is_file() or path.stat().st_size != item.size_bytes or sha(path) != item.sha256:
            raise WorkflowError('SOURCE_CHANGED', role)


def build_workflow_plan(*, mode, samples, targets, config, output, crispresso, runtime_digest,
        r1=None, r2=None, demux_root=None, barcodes=None, contrasts=None, tolerance_policies=None,
        title=DEFAULT_TITLE, analysis_r1_trim_5p=None, analysis_r2_trim_5p=None):
    """Resolve and validate a deterministic DAG without writing any workspace files."""
    try:
        if mode not in ('run', 'analyze') or not isinstance(runtime_digest, str) or not runtime_digest.strip():
            raise WorkflowError('INVALID_OPTIONS', 'mode and explicit runtime digest are required')
        if not isinstance(title, str) or not title.strip():
            raise WorkflowError('INVALID_OPTIONS', 'report title must be nonblank')
        root = no_symlinks(output)
        paths = dict(samples=samples, targets=targets, config=config)
        for name, value in (('barcodes', barcodes), ('contrasts', contrasts), ('policies', tolerance_policies)):
            if value is not None:
                paths[name] = value
        if mode == 'run':
            if r1 is None or r2 is None or demux_root is not None:
                raise WorkflowError('INVALID_OPTIONS', 'run requires R1/R2 and no demux-root')
            paths.update(r1=r1, r2=r2)
        elif demux_root is None or r1 is not None or r2 is not None:
            raise WorkflowError('INVALID_OPTIONS', 'analyze requires demux-root and no raw FASTQ')
        inputs = {role: input_record(path, role, snapshot=role not in ('r1', 'r2')) for role, path in paths.items()}
        settings = load_config(Path(inputs['config'].source_path))
        if 'barcodes' not in inputs and settings.demux.profile == 'qi_hitom_v1':
            inputs['barcodes'] = input_record(bundled_catalog(), 'barcodes')
        catalog = load_catalog(Path(inputs['barcodes'].source_path)) if 'barcodes' in inputs else Catalog([], authoritative=False)
        sample_rows = sorted(load_samples(Path(inputs['samples'].source_path), catalog), key=lambda s: s.barcode_id)
        target_rows = sorted(load_targets(Path(inputs['targets'].source_path)), key=lambda t: (t.target_name, t.copy_name))
        if title == DEFAULT_TITLE and target_rows[0].analysis_mode == 'indel_nuclease':
            title = 'Indel/nuclease amplicon analysis report'
        expected_samples = [s.barcode_id for s in sample_rows]
        expected_targets = sorted({t.target_name for t in target_rows})
        external = None
        if mode == 'analyze':
            external = no_symlinks(demux_root).resolve(strict=True)
            if root.is_relative_to(external) or external.is_relative_to(root):
                raise WorkflowError('EXTERNAL_INPUT_PROTECTION', 'workspace and external archive must be separate')
            verified = verify_demux_output(external)
            _demux_samples(verified, sample_rows)
            for record in inventory(external, '01_demux_QC') + inventory(external, '02_demultiplexed_fastq'):
                role = 'external_demux/' + record.path
                inputs[role] = input_record(external / record.path, role, snapshot=False)
        if any(Path(i.source_path).is_relative_to(root) for i in inputs.values()):
            raise WorkflowError('EXTERNAL_INPUT_PROTECTION', 'input files cannot be inside the workflow workspace')
        trims = PreparationConfig(r1_analysis_trim_5p=analysis_r1_trim_5p, r2_analysis_trim_5p=analysis_r2_trim_5p)
        if (analysis_r1_trim_5p is None) != (analysis_r2_trim_5p is None):
            raise WorkflowError('INVALID_OPTIONS', 'supply both analysis trim sizes')
        core = resolve_executable(str(crispresso))
        backend = Backend(executable=core.path, executable_sha256=sha(core.path), version=core.version, runtime_digest=runtime_digest)
        plan = Plan(mode=mode, output=str(root), expected_samples=expected_samples, expected_targets=expected_targets,
            samples=[s.model_dump(mode='json') for s in sample_rows], targets=target_rows,
            nodes=dag(mode, expected_samples, expected_targets), inputs=inputs,
            normalized_options=dict(title=title, preparation=trims.model_dump(mode='json'),
                demux_config=settings.model_dump(mode='json'), external_demux=str(external) if external else None,
                routing_policy=asdict(RoutingPolicy()), routing_policy_identity=policy_identity(RoutingPolicy()),
                statistics_mode='stats' if contrasts is not None else 'summarize',
                analysis_modes=sorted({t.analysis_mode for t in target_rows}),
                scientific_configuration=[scientific_target(t) for t in target_rows]),
            software_identity=software_identity(), backend_identity=backend)
        verify_inputs(inputs)
        return plan
    except WorkflowError:
        raise
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        raise WorkflowError('INVALID_WORKFLOW_INPUT', str(exc)) from exc


def _demux_samples(verified, samples):
    expected = {s.barcode_id if hasattr(s, 'barcode_id') else s['barcode_id']: s.model_dump() if hasattr(s, 'model_dump') else s for s in samples}
    actual = {s['barcode_id']: s for s in verified.summary['samples']}
    if set(actual) != set(expected):
        raise WorkflowError('DEMUX_SAMPLE_MISMATCH', 'verified demux inventory differs from samples.csv')
    for key in expected:
        if any(expected[key][field] != actual[key][field] for field in ('forward_barcode', 'reverse_barcode')):
            raise WorkflowError('DEMUX_SAMPLE_MISMATCH', 'barcode assignment differs from the immutable archive')


def stage_manifest_path(node):
    return 'workflow/stages/' + digest(node.stage_id) + '.json'


def scientific_target(target):
    return target.scientific_identity if target.analysis_mode == 'indel_nuclease' else dict(analysis_mode='precise_edit', **target.model_dump(mode='json'))


def nuclease_identity(plan, node):
    return dict(analysis_mode='indel_nuclease', identity_mechanism='single_copy_identity',
        sample_id=node.sample_id, targets=[scientific_target(t) for t in targets_for(plan,node)],
        analysis_manifest_sha256=sha(Path(plan.output)/'analysis/analysis_manifest.json'))


def targets_for(plan, node):
    return [t for t in plan.targets if t.target_name == node.target_name]


def inputs_for(plan, node):
    kind = node.stage_kind
    roles = dict(raw_inputs=['r1', 'r2'], demux=['r1', 'r2', 'samples', 'config', 'barcodes'],
        analysis=['samples', 'config', 'barcodes'] if plan.mode == 'analyze' else [],
        routing=['targets'], metrics=['policies'], statistics=['samples', 'contrasts'],
        metrics_manifest=[], report=[]).get(kind, [])
    if kind == 'external_demux':
        roles = [r for r in plan.inputs if r.startswith('external_demux/')]
    return {r: plan.inputs[r] for r in roles if r in plan.inputs}


def parameters_for(plan, node):
    kind, options = node.stage_kind, plan.normalized_options
    if kind == 'demux':
        return {'config': options['demux_config']}
    if kind == 'analysis':
        return {'preparation': options['preparation']}
    if kind in ('routing', 'metrics'):
        return dict(sample_id=node.sample_id, targets=[scientific_target(t) for t in targets_for(plan, node)],
                    **({'policy': options['routing_policy'], 'policy_identity': options['routing_policy_identity']} if kind == 'routing' and targets_for(plan,node)[0].analysis_mode == 'precise_edit' else {}))
    if kind == 'statistics':
        return {'mode': options['statistics_mode']}
    if kind == 'report':
        return {'title': options['title']}
    return {}


def output_identity(manifest):
    return digest(dict(signature=manifest.stage_signature_sha256, status=manifest.status,
                       artifacts=[a.model_dump() for a in manifest.output_artifacts], reasons=manifest.reason_codes))


def dependency(root, node, manifest):
    return Dependency(manifest=artifact(root, owned(root, stage_manifest_path(node))),
        stage_signature_sha256=manifest.stage_signature_sha256, output_identity_sha256=output_identity(manifest))


def signature(plan, node, dependencies):
    return digest(dict(workflow_contract_version='m7-v1', node=node.model_dump(mode='json'),
        software=plan.software_identity.model_dump(), backend=plan.backend_identity.model_dump() if node.stage_kind == 'metrics' else None,
        parameters=parameters_for(plan, node), inputs={k:dict(sha256=v.sha256, size_bytes=v.size_bytes) for k,v in inputs_for(plan,node).items()},
        dependencies={k:dict(stage_signature_sha256=v.stage_signature_sha256, output_identity_sha256=v.output_identity_sha256)
                      for k,v in dependencies.items()}))


def _file(plan, role):
    item = plan.inputs[role]
    return owned(Path(plan.output), item.snapshot) if item.snapshot else Path(item.source_path)


def _demux_root(plan):
    return owned(Path(plan.output), 'demux') if plan.mode == 'run' else Path(plan.normalized_options['external_demux'])


def _metrics_results(plan):
    root = Path(plan.output)
    expected = {(n.sample_id, n.target_name): owned(root, n.output_path + '/result.json')
                for n in plan.nodes if n.stage_kind == 'metrics'}
    actual = sorted(owned(root, 'metrics').rglob('result.json'))
    if set(actual) != set(expected.values()):
        raise WorkflowError('METRICS_COVERAGE_MISMATCH', 'missing, duplicate or unexpected result paths')
    seen = set()
    for identity, path in expected.items():
        result = load(path, metric_model(read_json(path)))
        key = result.sample_id, result.target_id
        if key != identity or key in seen:
            raise WorkflowError('METRICS_IDENTITY_MISMATCH', str(identity))
        seen.add(key)
    return expected


def _manifest_csv(plan):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow(['result_json'])
    for _, path in sorted(_metrics_results(plan).items()):
        writer.writerow([path.relative_to(Path(plan.output) / 'metrics').as_posix()])
    return stream.getvalue()


def validate_stage(plan, node, status):
    """Validate existing outputs without invoking any scientific executor."""
    root = Path(plan.output)
    output = owned(root, node.output_path)
    kind = node.stage_kind
    if kind in ('raw_inputs', 'external_demux'):
        if read_json(output) != {k:v.model_dump() for k,v in inputs_for(plan,node).items()}:
            raise WorkflowError('INPUT_IDENTITY_MISMATCH', kind)
        if kind == 'external_demux':
            _demux_samples(verify_demux_output(_demux_root(plan)), plan.samples)
    elif kind == 'demux':
        _demux_samples(verify_demux_output(output), plan.samples)
    elif kind == 'analysis':
        data = verify_analysis_output(output).manifest
        if data['verified_demux_root'] != str(_demux_root(plan)) or set(data['samples']) != set(plan.expected_samples):
            raise WorkflowError('ANALYSIS_LINEAGE_MISMATCH', node.stage_id)
    elif kind == 'routing':
        targets = targets_for(plan, node)
        if targets[0].analysis_mode == 'indel_nuclease':
            if len(targets)!=1 or status!='COMPLETED' or read_json(output/'identity.json')!=nuclease_identity(plan,node):
                raise WorkflowError('NUCLEASE_IDENTITY_MISMATCH',node.stage_id)
            return
        gate = geometry(targets, min_distinguishing_sites=RoutingPolicy().min_distinguishing_sites)
        if gate['status'] == 'BLOCKED':
            if status != 'SKIPPED_SCIENTIFIC_GATE' or canonical(read_json(output / 'scientific_gate.json')) != canonical(gate):
                raise WorkflowError('ROUTING_GATE_MISMATCH', node.stage_id)
        else:
            if status != 'COMPLETED':
                raise WorkflowError('ROUTING_GATE_MISMATCH', node.stage_id)
            data = verify_routing_output(output)
            if (data['sample_id'] != node.sample_id or data['targets'] != [t.model_dump() for t in targets]
                    or data['analysis_root'] != str(root / 'analysis')
                    or data['policy_identity'] != policy_identity(RoutingPolicy())):
                raise WorkflowError('ROUTING_LINEAGE_MISMATCH', node.stage_id)
    elif kind == 'metrics':
        result = load(output / 'result.json', metric_model(read_json(output / 'result.json')))
        if getattr(result,'analysis_mode','precise_edit') != targets_for(plan,node)[0].analysis_mode:
            raise WorkflowError('METRICS_MODE_MISMATCH',node.stage_id)
        if result.sample_id != node.sample_id or result.target_id != node.target_name:
            raise WorkflowError('METRICS_IDENTITY_MISMATCH', node.stage_id)
        from peanalyzer.metrics.production import digest as metric_digest
        if result.provenance.target_definitions_sha256 != metric_digest([t.model_dump() for t in targets_for(plan,node)]):
            raise WorkflowError('METRICS_TARGET_MISMATCH', node.stage_id)
        if read_json(output / 'execution_failures.json'):
            raise WorkflowError('BACKEND_EXECUTION_FAILED', node.stage_id)
    elif kind == 'metrics_manifest':
        if output.read_text() != _manifest_csv(plan):
            raise WorkflowError('METRICS_COVERAGE_MISMATCH', 'manifest rows differ from the complete inventory')
    elif kind == 'statistics':
        result = load(output / 'result.json', statistics_model(read_json(output / 'result.json')))
        if result.input_manifest_hash != sha(root / 'metrics/manifest.csv') or result.sample_metadata_hash != plan.inputs['samples'].sha256:
            raise WorkflowError('STATISTICS_LINEAGE_MISMATCH', node.stage_id)
        expected = _metrics_results(plan)
        observed = {}
        for item in result.provenance.input_results:
            key = item.sample_id, item.target_name
            if key in observed or key not in expected or item.sha256 != sha(expected[key]) or item.source_result != expected[key].relative_to(root / 'metrics').as_posix():
                raise WorkflowError('STATISTICS_LINEAGE_MISMATCH', 'M4 inputs differ')
            observed[key] = item
        if set(observed) != set(expected):
            raise WorkflowError('STATISTICS_LINEAGE_MISMATCH', 'incomplete M4 source inventory')
        if result.provenance.invocation_parameters['command'] != plan.normalized_options['statistics_mode']:
            raise WorkflowError('STATISTICS_LINEAGE_MISMATCH', 'statistics mode differs')
        expected_hash = plan.inputs['contrasts'].sha256 if 'contrasts' in plan.inputs else None
        if result.provenance.contrast_specification_hash != expected_hash:
            raise WorkflowError('STATISTICS_LINEAGE_MISMATCH', 'contrast identity differs')
        for name in ('observations', 'group_summaries', 'contrasts'):
            if not (output / (name + '.tsv')).is_file():
                raise WorkflowError('MISSING_STAGE_OUTPUT', name)
    elif kind == 'report':
        manifest = load(output / 'report_manifest.json', report_model(read_json(output / 'report_manifest.json')))
        source = (root / 'statistics/result.json').read_bytes()
        if (output / 'source/result.json').read_bytes() != source or manifest.source_result_sha256 != sha(root / 'statistics/result.json'):
            raise WorkflowError('REPORT_SOURCE_MISMATCH', node.stage_id)
        actual = inventory(root, node.output_path)
        if {a.path for a in actual} != {node.output_path + '/' + a.path for a in manifest.artifacts} | {'report/report_manifest.json'}:
            raise WorkflowError('REPORT_INVENTORY_MISMATCH', node.stage_id)
        import xml.etree.ElementTree as ET
        page = (output / 'report.html').read_text()
        for item in manifest.artifacts:
            path = owned(root, node.output_path + '/' + item.path)
            if sha(path) != item.sha256:
                raise WorkflowError('REPORT_HASH_MISMATCH', item.path)
            if item.media_type == 'image/svg+xml':
                svg = path.read_text()
                ET.fromstring(svg)
                if svg not in page:
                    raise WorkflowError('REPORT_SVG_MISMATCH', item.path)
        if manifest.title != plan.normalized_options['title'] or manifest.package_version != plan.software_identity.pipeline_version:
            raise WorkflowError('REPORT_IDENTITY_MISMATCH', node.stage_id)


def execute_stage(plan, node, completed, argv):
    """Only dispatch existing stage APIs; never calculate scientific values here."""
    root, kind = Path(plan.output), node.stage_kind
    output = owned(root, node.output_path)
    status, reasons = 'COMPLETED', []
    if kind in ('raw_inputs', 'external_demux'):
        atomic_json(output, {k:v.model_dump() for k,v in inputs_for(plan,node).items()})
    elif kind == 'demux':
        demultiplex(r1=_file(plan,'r1'), r2=_file(plan,'r2'), samples_path=_file(plan,'samples'),
            config=load_config(_file(plan,'config')), output=output,
            barcodes_path=_file(plan,'barcodes') if 'barcodes' in plan.inputs else None, command_argv=argv)
    elif kind == 'analysis':
        prepare_analysis_fastqs(_demux_root(plan), output, PreparationConfig.model_validate(plan.normalized_options['preparation']))
    elif kind == 'routing':
        targets = targets_for(plan,node)
        if targets[0].analysis_mode == 'indel_nuclease':
            if len(targets)!=1:raise WorkflowError('MULTICOPY_NUCLEASE_UNSUPPORTED',node.stage_id)
            atomic_json(output/'identity.json',nuclease_identity(plan,node))
            return status,reasons
        gate = geometry(targets, min_distinguishing_sites=RoutingPolicy().min_distinguishing_sites)
        if gate['status'] == 'BLOCKED':
            atomic_json(output / 'scientific_gate.json', gate)
            status, reasons = 'SKIPPED_SCIENTIFIC_GATE', ['ROUTING_GEOMETRY_BLOCKED']
        else:
            route_analysis(root / 'analysis', node.sample_id, targets, output, RoutingPolicy())
    elif kind == 'metrics':
        route = completed[f'routing::{node.sample_id}::{node.target_name}']
        policies = None
        if 'policies' in plan.inputs:
            policies = yaml.load(_file(plan,'policies').read_text(), Loader=UniqueKeyLoader)
        if targets_for(plan,node)[0].analysis_mode == 'indel_nuclease':
            if policies is not None:raise WorkflowError('PE_POLICIES_IN_NUCLEASE_MODE',node.stage_id)
            run_nuclease_metrics(analysis_root=root/'analysis',sample_id=node.sample_id,targets=targets_for(plan,node),
                analysis_id='m7-'+digest([node.sample_id,node.target_name]),output=output,
                core=resolve_executable(plan.backend_identity.executable),runtime_digest=plan.backend_identity.runtime_digest)
            return status,reasons
        run_metrics(analysis_root=root / 'analysis', sample_id=node.sample_id, targets=targets_for(plan,node),
            analysis_id='m7-' + digest([node.sample_id, node.target_name]), output=output,
            core=resolve_executable(plan.backend_identity.executable),
            routing_root=root / route.node.output_path if route.status == 'COMPLETED' else None,
            runtime_digest=plan.backend_identity.runtime_digest, tolerance_policies=policies)
    elif kind == 'metrics_manifest':
        text = _manifest_csv(plan)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', newline='') as handle:
            handle.write(text)
    elif kind == 'statistics':
        options = dict(manifest_path=root / 'metrics/manifest.csv', samples_path=_file(plan,'samples'), output=output)
        if plan.normalized_options['statistics_mode'] == 'stats':
            stats(**options, contrasts_path=_file(plan,'contrasts'))
        else:
            summarize(**options)
    else:
        generate_report(result_path=root / 'statistics/result.json', output=output, title=plan.normalized_options['title'])
    return status, reasons


def _snapshots(plan):
    root = Path(plan.output)
    for item in plan.inputs.values():
        if item.snapshot:
            path = owned(root, item.snapshot)
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                if sha(path) != item.sha256:
                    raise WorkflowError('SNAPSHOT_CORRUPTED', item.snapshot)
            else:
                with path.open('xb') as handle:
                    handle.write(Path(item.source_path).read_bytes())
            if sha(path) != item.sha256:
                raise WorkflowError('SOURCE_CHANGED', item.source_path)


def force_closure(plan, families):
    families = set(families)
    if families - set(FORCE_FAMILIES) or plan.mode == 'analyze' and 'demux' in families:
        raise WorkflowError('INVALID_FORCE', 'unknown family or immutable external demux')
    selected = {n.stage_id for n in plan.nodes if 'all' in families or n.stage_kind in families}
    # Source records are owned bookkeeping, never the external inputs themselves.
    if plan.mode == 'run' and 'demux' in selected:
        selected.add('raw_inputs')
    if plan.mode == 'analyze' and 'all' in families:
        selected.add('external_demux')
    for node in plan.nodes:
        if selected.intersection(node.dependencies):
            selected.add(node.stage_id)
    return selected


def _graph_change(old, new, force):
    if {t.analysis_mode for t in old.targets}!={t.analysis_mode for t in new.targets}:
        raise WorkflowError('ANALYSIS_MODE_MISMATCH','start a new workspace for a different scientific mode')
    if old.mode != new.mode or old.output != new.output:
        raise WorkflowError('WORKFLOW_GRAPH_MISMATCH', 'mode/workspace cannot change')
    required = set()
    if old.expected_samples != new.expected_samples:
        required.add('demux' if new.mode == 'run' else 'analysis')
    if old.expected_targets != new.expected_targets:
        required.add('routing')
    selected = force_closure(new, force)
    if any(not all(n.stage_id in selected for n in new.nodes if n.stage_kind == kind) for kind in required):
        raise WorkflowError('WORKFLOW_GRAPH_MISMATCH', 'sample/target inventory changed without adequate force')
    if new.mode == 'analyze':
        old_inputs = {k:v for k,v in old.inputs.items() if k.startswith('external_demux/')}
        new_inputs = {k:v for k,v in new.inputs.items() if k.startswith('external_demux/')}
        if old_inputs != new_inputs:
            raise WorkflowError('EXTERNAL_DEMUX_CHANGED', 'start a new workspace for a different external archive')


def _invalidate(root, old, new, force):
    """Delete only fixed, validated plan-owned paths, never stored arbitrary paths."""
    nodes = {n.stage_id:n for p in (old,new) for n in p.nodes if n.stage_id in force_closure(p,force)}
    # Prove every deletion safe before mutating anything. Reject nested symlinks too.
    for node in nodes.values():
        path = owned(root,node.output_path)
        owned(root,stage_manifest_path(node))
        if path.exists() and path.is_dir():
            for child in path.rglob('*'):
                no_symlinks(child)
    marker = owned(root,'workflow_manifest.json')
    marker.unlink(missing_ok=True)
    for node in reversed(list(nodes.values())):
        path = owned(root,node.output_path)
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
        owned(root,stage_manifest_path(node)).unlink(missing_ok=True)


def _expected(plan, node, refs):
    api = API[node.stage_kind]
    if node.stage_kind in ('routing','metrics') and targets_for(plan,node)[0].analysis_mode=='indel_nuclease':
        api = 'single_copy_identity' if node.stage_kind=='routing' else 'run_nuclease_metrics'
    return dict(node=node, stage_signature_sha256=signature(plan,node,refs), dependencies=refs,
        input_artifacts=inputs_for(plan,node), normalized_parameters=parameters_for(plan,node),
        software_identity=plan.software_identity,
        backend_identity=plan.backend_identity if node.stage_kind == 'metrics' else None, api_call=api)


def _validate_completed(plan, node, refs):
    root = Path(plan.output)
    manifest = load(owned(root,stage_manifest_path(node)), StageManifest)
    for key,value in _expected(plan,node,refs).items():
        if getattr(manifest,key) != value:
            raise WorkflowError('STALE_STAGE_IDENTITY', key, node.stage_id)
    if inventory(root,node.output_path) != manifest.output_artifacts:
        raise WorkflowError('CORRUPTED_STAGE_OUTPUT', node.output_path, node.stage_id)
    verify_inputs(inputs_for(plan,node))
    validate_stage(plan,node,manifest.status)
    return manifest


def _verify_stages(plan):
    root, completed, identities = Path(plan.output), {}, {}
    verify_inputs(plan.inputs)
    for item in plan.inputs.values():
        if item.snapshot and sha(owned(root,item.snapshot)) != item.sha256:
            raise WorkflowError('SNAPSHOT_CORRUPTED', item.snapshot)
    expected_paths = {owned(root, stage_manifest_path(n)) for n in plan.nodes}
    if set(owned(root, 'workflow/stages').glob('*.json')) != expected_paths:
        raise WorkflowError('STAGE_INVENTORY_MISMATCH', 'missing or unexpected completion records')
    for node in plan.nodes:
        refs = {key:identities[key] for key in node.dependencies}
        try:
            result = _validate_completed(plan,node,refs)
        except Exception as exc:
            if isinstance(exc,WorkflowError):
                raise
            raise WorkflowError('INVALID_STAGE', str(exc), node.stage_id) from exc
        completed[node.stage_id] = result
        identities[node.stage_id] = dependency(root,node,result)
    return completed, identities


def verify_workflow_output(output):
    """Read-only verification. Never resolves/probes or executes the backend."""
    try:
        root = no_symlinks(output)
        manifest = load(owned(root,'workflow_manifest.json'),WorkflowManifest)
        if manifest.plan.path != 'workflow/plan.json':
            raise WorkflowError('INVALID_COMPLETION', 'unexpected plan path')
        plan = load(verify_artifact(root,manifest.plan),Plan)
        if plan.output != str(root) or manifest.mode != plan.mode or manifest.software_identity != plan.software_identity or manifest.input_inventory != plan.inputs:
            raise WorkflowError('INVALID_COMPLETION','plan identity differs')
        if manifest.analysis_modes != sorted({t.analysis_mode for t in plan.targets}):
            raise WorkflowError('INVALID_COMPLETION','analysis mode differs')
        _, refs = _verify_stages(plan)
        expected = {key:ref.manifest for key,ref in refs.items()}
        if manifest.stage_inventory != expected:
            raise WorkflowError('INVALID_COMPLETION','stage inventory differs')
        if manifest.statistics_result != artifact(root,owned(root,'statistics/result.json')) or manifest.report_manifest != artifact(root,owned(root,'report/report_manifest.json')):
            raise WorkflowError('INVALID_COMPLETION','final artifacts differ')
        return manifest
    except WorkflowError:
        raise
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise WorkflowError('INVALID_WORKFLOW_OUTPUT',str(exc)) from exc


def _check_execution_scope(plan):
    for name in plan.expected_targets:
        rows=[t for t in plan.targets if t.target_name==name]
        if rows[0].analysis_mode=='indel_nuclease':
            if len(rows)!=1:raise WorkflowError('MULTICOPY_NUCLEASE_UNSUPPORTED',name)
            if 'policies' in plan.inputs:raise WorkflowError('PE_POLICIES_IN_NUCLEASE_MODE',name)
    if len(plan.expected_targets) != 1:
        raise WorkflowError('MULTI_TARGET_EXECUTION_UNSUPPORTED',
            'M4 requires target-specific eligible reads; no qualified target-selection contract exists. '
            'Use one biological target per workflow. Multi-target planning remains supported.')


def execute_workflow(*, resume=False, force=(), argv=None, observer=None, expected_plan=None, expected_output_parent=None, expected_recovery_identity=None, **inputs):
    """Run/resume a workspace under one exclusive invocation lock."""
    def observe(status, node=None, reasons=(), code=None):
        # Only detached presentation values cross this boundary; no return value
        # affects execution, and observer failures do not change scientific work.
        if observer is not None:
            try:
                observer(dict(status=status,stage_id=node.stage_id if node else None,
                    stage_kind=node.stage_kind if node else None,reason_codes=list(reasons),code=code))
            except Exception:
                pass
    if force and not resume:
        raise WorkflowError('INVALID_FORCE','force requires resume')
    root = no_symlinks(inputs['output'])
    root.parent.mkdir(parents=True,exist_ok=True)
    lock = no_symlinks(root.with_name('.'+root.name+'.m7-lock'))
    try:
        descriptor = os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError as exc:
        raise WorkflowError('WORKFLOW_LOCKED',str(lock)) from exc
    os.close(descriptor)
    plan, session, active = None, None, None
    workspace_owned = False
    active_node = None
    started = utc()
    executed, reused = [], []
    session_id = uuid.uuid4().hex
    supplied_argv = list(argv or [])
    try:
        if not resume and root.exists():
            raise WorkflowError('OUTPUT_EXISTS','initial workflow root must be new')
        if resume and not root.is_dir():
            raise WorkflowError('INVALID_WORKSPACE','resume requires an existing workspace')
        candidate = build_workflow_plan(**inputs)
        _check_execution_scope(candidate)
        if expected_plan is not None and candidate != expected_plan:
            raise WorkflowError('ACCEPTED_PLAN_CHANGED','Resolved execution no longer matches the accepted plan')
        plan = candidate
        old = load(owned(root,'workflow/plan.json'),Plan) if resume else plan
        _graph_change(old,plan,force)
        no_symlinks(root)
        if expected_output_parent is not None:
            parent_stat=root.parent.stat()
            if (parent_stat.st_dev,parent_stat.st_ino) != tuple(expected_output_parent):
                raise WorkflowError('OUTPUT_CHANGED','Output parent identity changed')
        if resume:
            from peanalyzer.workflow_recovery import preflight_resume, workspace_identity
            # Failure before commitment leaves every scientific byte/manifest intact.
            preflight = preflight_resume(old,plan,force)
            if expected_recovery_identity is not None and digest(preflight)!=expected_recovery_identity:
                raise WorkflowError('RECOVERY_PLAN_CHANGED','Confirmed recovery no longer matches preflight')
            verify_inputs(plan.inputs)
            if workspace_identity(root)!=preflight['workspace_identity']:
                raise WorkflowError('RECOVERY_PLAN_CHANGED','Workspace changed before recovery commitment')
            workspace_owned=True
        else:
            try:
                root.mkdir()
            except FileExistsError as exc:
                raise WorkflowError('OUTPUT_EXISTS','Output appeared before execution; new execution only') from exc
            workspace_owned=True
        if force:
            _invalidate(root,old,plan,force)
        _snapshots(plan)
        # Keep plan/input history; current plan is never an assertion of completion.
        for item in (old,plan):
            atomic_json(owned(root,'workflow/plans/'+digest(item)+'.json'),item)
        atomic_json(owned(root,'workflow/plan.json'),plan)
        completed, identities = {}, {}
        for node in plan.nodes:
            active = node.stage_id
            active_node = node
            refs = {key:identities[key] for key in node.dependencies}
            path = owned(root,stage_manifest_path(node))
            if path.exists():
                result = _validate_completed(plan,node,refs)
                reused.append(node.stage_id)
            else:
                observe('RUNNING',node)
                if owned(root,node.output_path).exists():
                    raise WorkflowError('ORPHANED_STAGE_OUTPUT',node.output_path,node.stage_id)
                stage_start = utc()
                verify_inputs(inputs_for(plan,node))
                status, reasons = execute_stage(plan,node,completed,supplied_argv)
                validate_stage(plan,node,status)
                # Recheck exact source/dependency bytes before completion publication.
                verify_inputs(inputs_for(plan,node))
                for key,ref in refs.items():
                    verify_artifact(root,ref.manifest)
                    parent = completed[key]
                    if inventory(root,parent.node.output_path) != parent.output_artifacts:
                        raise WorkflowError('DEPENDENCY_CHANGED',key,node.stage_id)
                if software_identity() != plan.software_identity:
                    raise WorkflowError('SOFTWARE_CHANGED','package identity changed during execution',node.stage_id)
                if node.stage_kind == 'metrics' and sha(plan.backend_identity.executable) != plan.backend_identity.executable_sha256:
                    raise WorkflowError('BACKEND_CHANGED','executable changed during execution',node.stage_id)
                result = StageManifest(**_expected(plan,node,refs),status=status,reason_codes=reasons,
                    output_artifacts=inventory(root,node.output_path),started_at=stage_start,ended_at=utc(),
                    validation=['stage_contract','output_inventory_sha256','source_identity','dependency_identity'])
                atomic_json(path,result)
                executed.append(node.stage_id)
            completed[node.stage_id] = result
            identities[node.stage_id] = dependency(root,node,result)
            observe('REUSED' if node.stage_id in reused else result.status,node,result.reason_codes)
        active = 'final_validation'
        active_node = None
        observe('FINAL_VALIDATION')
        _, identities = _verify_stages(plan)
        session = Session(session_id=session_id,mode=plan.mode,resume=resume,force=sorted(set(force)),started_at=started,
            ended_at=utc(),executed_stages=executed,reused_stages=reused,failed_stage=None,argv=supplied_argv,cwd=os.getcwd())
        final = owned(root,'workflow_manifest.json')
        if final.exists() and not executed:
            verify_workflow_output(root)
        else:
            manifest = WorkflowManifest(status='COMPLETED',mode=plan.mode,software_identity=plan.software_identity,
                analysis_modes=sorted({t.analysis_mode for t in plan.targets}),
                plan=artifact(root,owned(root,'workflow/plan.json')),input_inventory=plan.inputs,
                stage_inventory={key:ref.manifest for key,ref in identities.items()},session=session,
                statistics_result=artifact(root,owned(root,'statistics/result.json')),
                report_manifest=artifact(root,owned(root,'report/report_manifest.json')),limitations=LIMITATIONS)
            atomic_json(final,manifest)
        return dict(workflow_contract_version='m7-v1',output=str(root),mode=plan.mode,
            executed_stages=executed,reused_stages=reused,
            metrics_results=len([n for n in plan.nodes if n.stage_kind=='metrics']),
            statistics_mode=plan.normalized_options['statistics_mode'],report_path=str(root/'report/report.html'),
            workflow_manifest_sha256=sha(final))
    except BaseException as exc:
        # Initial OUTPUT_EXISTS and foreign-lock failures must never alter that workspace.
        observe('FAILED',active_node,code=getattr(exc,'code','STAGE_EXECUTION_FAILED'))
        if plan is not None and workspace_owned:
            owned(root,'workflow_manifest.json').unlink(missing_ok=True)
            if root.is_dir():
                atomic_json(owned(root,f'workflow/failures/{session_id}.json'),dict(stage_id=active,
                    error_class=type(exc).__name__,code=getattr(exc,'code','STAGE_EXECUTION_FAILED'),message=str(exc),
                    started_at=started,ended_at=utc(),session_id=session_id))
        if isinstance(exc,(KeyboardInterrupt,SystemExit,WorkflowError)):
            raise
        raise WorkflowError('STAGE_EXECUTION_FAILED',str(exc),active) from exc
    finally:
        try:
            if plan is not None and workspace_owned and root.is_dir():
                if session is None:
                    session = Session(session_id=session_id,mode=plan.mode,resume=resume,force=sorted(set(force)),started_at=started,
                        ended_at=utc(),executed_stages=executed,reused_stages=reused,failed_stage=active,argv=supplied_argv,cwd=os.getcwd())
                atomic_json(owned(root,f'workflow/sessions/{session_id}.json'),session)
        finally:
            lock.unlink()


def resume_workflow(**inputs):
    return execute_workflow(resume=True,**inputs)
