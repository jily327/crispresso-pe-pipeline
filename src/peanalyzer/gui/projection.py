"""Copy authoritative stored values into explicit UI models; never run science."""
import json
from pathlib import Path
from peanalyzer import __version__
from peanalyzer.gui.models import (FieldValue, Value, Observation, Group, Contrast,
    Population, Bin, ClassValue, NucleaseDetail, Allele, Stage, WorkspaceView)
from peanalyzer.workflow_models import Plan, StageManifest
from peanalyzer.workflow_storage import digest, WorkflowError
from peanalyzer.result_dispatch import statistics_model, metric_model

LABELS = {'total_precise_pe': 'Exact intended PE',
    'target_crispresso_native_pe': 'CRISPResso Prime-edited reference fraction', 'indel_fraction': 'Indel fraction'}


def percentage(fraction):
    """Format a stored fraction; never derive a fraction from counts."""
    return None if fraction is None else f'{fraction * 100:.6g}%'


def fields(values):
    """Literal evidence table, retaining integer precision and JSON scalar types."""
    return [FieldValue(name=k, value=None if v is None else json.dumps(v, ensure_ascii=True, sort_keys=True))
            for k, v in values.items()]


def ratio(value):
    return dict(numerator=None if value.numerator is None else str(value.numerator),
        denominator=None if value.denominator is None else str(value.denominator),
        fraction=value.fraction, percentage=percentage(value.fraction))


def series(value):
    return digest({k: getattr(value, k) for k in ('target_name', 'metric_name', 'copy_name',
        'policy_id', 'policy_definition', 'population_scope', 'routing_conditioned')})


def condition(c):
    return f'{c.editor} / {c.treatment} / dpi {c.dpi}'


def label(name):
    if name.startswith("intended_sites."):
        from peanalyzer.site_series import measurement_labels
        method, outcome, _ = measurement_labels(name)
        return f"{method} · {outcome}"
    if name.endswith('_crispresso_native_pe'):
        return 'CRISPResso Prime-edited reference fraction'
    if name.endswith('_precise_pe'):
        return 'Exact intended PE'
    return LABELS.get(name, name.replace('_', ' '))


def allele_rows(alleles, source):
    return [Allele(row_id=f'{source.artifact_id}:{i}',reads=str(a.reads),product_class=a.product_class,
                inserted_bp=str(a.n_inserted),deleted_bp=str(a.n_deleted),mutated_bp=str(a.n_mutated),net_delta=str(a.net_delta_bp),
                aligned_sequence=a.authoritative_fields['Aligned_Sequence'],reference_sequence=a.authoritative_fields['Reference_Sequence'],
                original_percentage=a.authoritative_fields['%Reads']) for i,a in enumerate(alleles)]


def strict_result(raw, kind):
    key, supported, dispatch = ('statistics_contract_version', {'m5-v1', 'indel-nuclease-stats-v1'}, statistics_model) if kind == 'statistics' else (
        'metric_contract_version', {'m4-v1', 'indel-nuclease-v1', 'empty-nuclease-control-v1', 'indel-nuclease-multicopy-v1'}, metric_model)
    if type(raw.get('schema_version')) is not int or raw['schema_version'] != 1 or raw.get(key) not in supported:
        raise WorkflowError('UNSUPPORTED_CONTRACT', 'Unsupported '+kind+' contract')
    return dispatch(raw).model_validate(raw)


def project(root, manifest, read, sources, workspace_id, title, snapshot_id):
    plan = Plan.model_validate(read(manifest.plan.path))
    mode = manifest.analysis_modes[0]
    if len(manifest.analysis_modes) != 1:
        raise WorkflowError('UNSUPPORTED_CONTRACT', 'Viewer requires one scientific mode')
    stats = strict_result(read(manifest.statistics_result.path), 'statistics')
    stats_source = sources[manifest.statistics_result.path]
    metrics, metric_sources, contracts = {}, {}, {stats.statistics_contract_version, manifest.workflow_contract_version}
    from peanalyzer.gui.scientific_projection import multicopy_nuclease_panels, panel, reference_panels, site_panels, window_panels
    scientific_panels = []
    for node in plan.nodes:
        if mode == 'precise_edit' and node.stage_kind == 'routing':
            for name in ('geometry.json', 'scientific_gate.json'):
                geometry_path = f'{node.output_path}/{name}'
                if geometry_path in sources:
                    scientific_panels.extend(reference_panels(read(geometry_path), sources[geometry_path], node.sample_id, node.target_name))
        if node.stage_kind != 'metrics':
            continue
        path = node.output_path+'/result.json'
        result = strict_result(read(path), 'metric')
        metrics[(result.sample_id, result.target_id)] = result
        metric_sources[(result.sample_id, result.target_id)] = sources[path]
        contracts.add(result.metric_contract_version)
        qc_path = node.output_path + '/sample_qc.json'
        if qc_path in sources:
            qc = read(qc_path)
            scientific_panels.append(panel(result.sample_id, result.target_id, 'Sample depth and role', 'Prepared read pairs',
                qc['depth_status'], sources[qc_path], evidence=qc,
                definition='Depth is compared with the configured minimum for prepared read pairs. Empty controls have no measured editing fraction.'))
        if mode == 'precise_edit':
            scientific_panels.extend(window_panels(result, sources[path]))
            sites_path = node.output_path + '/intended_sites.json'
            if sites_path in sources:
                payload = read(sites_path)
                scientific_panels.extend(site_panels(payload, sources[sites_path], result.sample_id, result.target_id,
                                                    canonical_record=result.target_metrics.total_precise_pe))
                contracts.add(payload['contract'])
    observations, populations, details, alleles = [], [], [], {}
    from peanalyzer.schemas import BIOLOGICAL_ROLE_POLICY, biological_role
    has_role_policy = stats.provenance.invocation_parameters.get("biological_role_policy") == BIOLOGICAL_ROLE_POLICY
    for o in stats.observations:
        key = (o.sample_id, o.target_name)
        if key not in metrics:
            raise WorkflowError('MISSING_METRIC', 'Observation has no verified metric source')
        m = metrics[key]
        source = metric_sources[key]
        site_labels = None
        if o.metric_contract_version == 'intended-sites-v1.1':
            from peanalyzer.site_series import ARTIFACT, measurement_labels
            source = sources[(Path(source.name).parent / ARTIFACT).as_posix()]
            if source.sha256 != m.provenance.artifacts[ARTIFACT].sha256:
                raise WorkflowError('SOURCE_IDENTITY_MISMATCH', 'Declared site observation hash differs')
            site_labels = measurement_labels(o.metric_name)
        # M5 already verifies counts/series against source metrics. Preserve that exact join.
        if (Path(stats.provenance.manifest_path).parent / o.source_result).resolve() != (root/source.name).resolve():
            raise WorkflowError('SOURCE_IDENTITY_MISMATCH', 'Observation source differs')
        record = None
        if mode == 'precise_edit':
            if o.copy_name is None:
                record = getattr(m.target_metrics, o.metric_name, None)
            elif o.copy_name in m.copies:
                record = next((r for r in (m.copies[o.copy_name].native, m.copies[o.copy_name].precise)
                               if r.metric_name == o.metric_name), None)
        evidence = fields(record.model_dump(exclude={'metric_name','reason_codes'}) if record else {})
        observations.append(Observation(**ratio(o), sample_role=o.sample_role,
            biological_eligible=biological_role(o.sample_role) if has_role_policy else None, observation_id=digest([o.sample_id,series(o),o.population_id]),
            series_id=series(o), sample_id=o.sample_id, sample_name=o.sample_name, editor=o.editor,
            treatment=o.treatment, dpi=str(o.dpi), biological_replicate=o.biological_replicate,
            block_id=o.block_id, paired=o.paired, target=o.target_name, copy_name=o.copy_name,
            policy_id=o.policy_id, policy=fields(o.policy_definition or {}), metric_name=o.metric_name,
            label=label(o.metric_name), population_id=o.population_id, population_scope=o.population_scope,
            routing_conditioned=o.routing_conditioned, status=o.status, reasons=o.reason_codes,
            assessment_stage=site_labels[0] if site_labels else record.assessment_stage if record else ('backend_aligned_products' if mode=='indel_nuclease' else 'See stored policy evidence'),
            backend_counts_role=('allele table' if '.core_alleles.' in o.metric_name else 'prepared physical pairs') if site_labels else record.backend_counts_role if record else ('metric_filter' if mode=='indel_nuclease' else 'See stored policy evidence'),
            numerator_label=(site_labels[1] if site_labels else 'Reads assigned to the Prime-edited reference' if record and record.metric_family=='native'
                else 'Exact intended PE products' if record else ('Reads with ' + label(o.metric_name).removesuffix(' fraction') + ' in the selected window')
                if mode=='indel_nuclease' else 'Stored metric numerator'),
            definition=(f'{site_labels[1]} / {site_labels[2].lower()} in this population. {site_labels[0]}.' if site_labels else 'Prime-edited reference-assigned reads / authoritative aligned reads; not CRISPResso Modified%.' if record and record.metric_family=='native'
                else 'Exact intended PE / (exact WT + exact intended PE). Different numerator and denominator from the CRISPResso reference fraction; neither is a lower bound.' if record
                else 'Reads with the named outcome divided by assessable aligned reads in the selected window and population.' if mode=='indel_nuclease'
                else 'Stored metric fraction for the authoritative population and selected window/policy.'),
            denominator_label=(site_labels[2] if site_labels else 'Assessable aligned reads in this population' if m.metric_contract_version=='indel-nuclease-multicopy-v1' else 'Authoritative aligned reads' if mode=='indel_nuclease' or (record and record.metric_family=='native')
                else 'Exact WT + exact PE products' if record else 'Stored policy-specific denominator'), source=source, evidence=evidence))
    for key, m in metrics.items():
        source = metric_sources[key]
        if mode == 'precise_edit':
            populations.append(Population(sample_id=m.sample_id,name='Prepared / copy routing',role='Separate prepared and routing populations',counts=fields(m.qc.model_dump()),source=source))
            for record in [m.target_metrics.total_precise_pe,m.target_metrics.target_crispresso_native_pe,
                           *[r for c in m.copies.values() for r in (c.precise,c.native)]]:
                populations.append(Population(sample_id=m.sample_id,name=record.metric_name,
                    role=record.assessment_stage+' / '+record.backend_counts_role,
                    counts=fields(record.model_dump(exclude={'metric_name'})), source=source))
        elif m.metric_contract_version == 'empty-nuclease-control-v1':
            alleles[m.sample_id] = ([], source)
        elif m.metric_contract_version == 'indel-nuclease-multicopy-v1':
            scientific_panels.extend(multicopy_nuclease_panels(m, source))
            alleles[m.sample_id] = (allele_rows(m.combined.alleles, source), source)
        else:
            populations.append(Population(sample_id=m.sample_id,name='Single-copy identity → CRISPResso alignment → ordinary population',
                role='Experimental single-copy identity; no PE copy-routing partition',
                counts=fields({k:getattr(m,k) for k in ('backend_input_reads','reads_after_preprocessing','aligned_reads','unaligned_reads','class_counts')}),source=source))
            if any(p.sample_id == m.sample_id and p.method == 'Sample depth and role' for p in scientific_panels):
                from peanalyzer.gui.scientific_projection import window_name
                window = m.provenance.scientific_identity['resolved_window']
                scientific_panels.append(panel(m.sample_id, m.target_id, window_name(window), m.target.copy_name,
                    m.status, source, reasons=m.reason_codes, evidence=window,
                    definition='The selected window uses zero-based inclusive coordinates on the supplied WT amplicon.'))
            rows = allele_rows(m.alleles, source)
            alleles[m.sample_id] = (rows, source)
            expected = m.provenance.scientific_identity['backend_settings']
            actual = m.provenance.execution['resolved_backend_arguments']
            # Local file paths are unnecessary in the scientific configuration display.
            safe_actual = {k: ('<local path>' if k in ('fastq_r1','fastq_r2','output_folder','config_file') and v else v) for k,v in actual.items()}
            details.append(NucleaseDetail(sample_id=m.sample_id,target=m.target_id,status=m.status,
                window=fields(m.provenance.scientific_identity['resolved_window']),
                classes=[ClassValue(name=k,**ratio(m.metrics[k+'_fraction'])) for k in ('unmodified','substitution_only','indel_only','indel_plus_substitution')],
                overlapping=[ClassValue(name=k,**ratio(m.metrics[k])) for k in ('insertion_containing_fraction','deletion_containing_fraction','substitution_containing_fraction','insertion_and_deletion_containing_fraction','any_modification_fraction')],
                bins=[Bin(net_size=k,**ratio(v)) for k,v in sorted(m.fraction_of_indel_reads_by_net_size.items(),key=lambda x:int(x[0]))],
                allele_count=str(len(rows)),expected_configuration=fields(expected),resolved_configuration=fields(safe_actual),source=source))
    demux_path = 'demux/01_demux_QC/demux_summary.json'
    if demux_path in sources:
        populations.insert(0,Population(sample_id=None,name='Demultiplexing read pairs',role='Raw pool terminal categories',
            counts=fields(read(demux_path)),source=sources[demux_path]))
    analysis_path = 'analysis/analysis_manifest.json'
    if analysis_path in sources:
        manifest_qc = read(analysis_path).get('trim_boundary_qc')
        if manifest_qc:
            populations.append(Population(sample_id=None, name='Analysis trim boundaries', role='Raw mate offsets after preparation',
                                          counts=fields(manifest_qc), source=sources[analysis_path]))
    groups = [Group(series_id=series(g),metric_name=g.metric_name,label=label(g.metric_name),condition=condition(g.condition),
        expected_n=str(g.expected_sample_count),reportable_n=str(g.reportable_count),mean=g.mean_biological_sample_fraction,
        mean_percentage=percentage(g.mean_biological_sample_fraction),minimum=g.minimum_biological_sample_fraction,
        descriptive_statistics_version=getattr(g, 'descriptive_statistics_version', None),
        sample_sd=getattr(g, 'sample_sd_biological_sample_fraction', None),
        sample_sd_percentage=percentage(getattr(g, 'sample_sd_biological_sample_fraction', None)),
        pooled_read_fraction=g.pooled_read_fraction,
        maximum=g.maximum_biological_sample_fraction,median=g.median_biological_sample_fraction,
        points=fields({p.sample_name:p.fraction for p in g.source_fractions}),
        availability=fields({p.sample_name:dict(status=p.status,reasons=p.reason_codes) for p in g.sample_assessments}),source=stats_source) for g in stats.group_summaries]
    contrasts = [Contrast(contrast_id=c.contrast_id,series_id=series(c),metric_name=c.metric_name,group_a=condition(c.group_a),group_b=condition(c.group_b),
        effect=c.difference_in_biological_sample_fraction,p=c.p_value,q=c.q_value,expected_a=str(c.expected_group_a_count),expected_b=str(c.expected_group_b_count),
        used_a=str(c.used_group_a_count),used_b=str(c.used_group_b_count),family=c.family_id,pairing_mode=c.pairing_mode,blocks=c.complete_blocks,
        exclusions=fields({b.block_id:b.model_dump() for b in c.excluded_blocks}),status=c.status,reasons=c.reason_codes,source=stats_source) for c in stats.contrasts]
    stages=[]
    for stage_id, ref in manifest.stage_inventory.items():
        s=StageManifest.model_validate(read(ref.path))
        stages.append(Stage(stage_id=stage_id,label=('Single-copy identity check' if len(plan.targets)==1 else 'Copy marker assessment') if mode=='indel_nuclease' and s.node.stage_kind=='routing' else s.node.stage_kind,
            status=s.status,history='reused' if stage_id in manifest.session.reused_stages else 'executed',signature=s.stage_signature_sha256,started_at=s.started_at,ended_at=s.ended_at))
    provenance = fields(dict(viewer_version=__version__,source_software=manifest.software_identity.model_dump(),
        analysis_mode=mode,observed_CRISPResso_version=plan.backend_identity.version,declared_qualified_runtime=plan.backend_identity.runtime_digest,
        observed_executable=plan.backend_identity.executable,observed_executable_sha256=plan.backend_identity.executable_sha256,
        runtime_provenance='Image identity unverified; the qualified digest is a declaration, not attestation. Executable hash may identify a wrapper only.',
        input_identities={k:dict(sha256=v.sha256,size_bytes=str(v.size_bytes)) for k,v in manifest.input_inventory.items()},
        limitations=manifest.limitations,statistics_source_sha256=manifest.statistics_result.sha256,report_manifest_sha256=manifest.report_manifest.sha256))
    native = False
    for source in sources.values():
        if source.name.startswith('metrics/') and source.name.endswith('/CRISPResso2_info.json'):
            filename = read(source.name).get('running_info', {}).get('report_filename')
            if isinstance(filename, str) and Path(filename).name == filename and filename.endswith('.html'):
                parent = Path(source.name).parent
                native = native or any((base/filename).as_posix() in sources for base in (parent,parent.parent))
    return WorkspaceView(workspace_id=workspace_id,label=title,snapshot_id=snapshot_id,mode=mode,targets=plan.expected_targets,
        contracts=sorted(contracts),observations=sorted(observations,key=lambda o:(o.sample_id,o.series_id,o.observation_id)),groups=groups,contrasts=contrasts,
        minimum_biological_replicates=stats.provenance.invocation_parameters.get('minimum_biological_replicates'),
        populations=populations,nuclease=details,scientific_panels=scientific_panels,provenance=provenance,stages=stages,artifacts=list(sources.values()),
        native_html='Available for download only' if native else 'Not produced'), alleles
