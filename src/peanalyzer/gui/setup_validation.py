"""Compile previews with existing metadata, geometry and DAG authorities only."""
import csv
import io
import json
from pydantic import ValidationError
from peanalyzer import __version__
from peanalyzer.schemas import Config, Sample, Target, Identifier
from peanalyzer.nuclease.targets import NucleaseTarget
from peanalyzer.validation import load_samples, load_targets, _csv_value, metadata_warnings
from peanalyzer.barcodes import Catalog, bundled_catalog, load_catalog, validate_catalog_matching, extraction_rules
from peanalyzer.analysis_fastq import PreparationConfig, resolve_trims
from peanalyzer.fastq import paired_fastq
from peanalyzer.demux_verify import verify_demux_output
from peanalyzer.geometry import geometry
from peanalyzer.workflow import _demux_samples, scientific_target
from peanalyzer.workflow_models import dag
from peanalyzer.routing import RoutingPolicy, policy_identity
from peanalyzer.metrics.production import RUNTIME_DIGEST
from peanalyzer.workflow_storage import digest, owned
from peanalyzer.gui.projection import fields
from peanalyzer.gui.setup_models import (SetupIssue, TargetPreview, PlanPreview, PreviewStage,
    DraftValidation)

BASE = '40bd8ad8844fd07ce8a138b5520f7f0ec948030f'


class MemoryCSV:
    """Use the exact backend CSV loaders without writing draft metadata to disk."""
    def __init__(self, rows, label):
        self.label = label
        stream = io.StringIO(newline='')
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows([{k: str(v).lower() if isinstance(v, bool) else v for k,v in r.items()} for r in rows])
        self.text = stream.getvalue()

    def open(self, **kwargs):
        return io.StringIO(self.text, newline='')

    def __str__(self):
        return self.label


def target_values(row):
    raw = row.model_dump()
    if raw['analysis_mode'] == 'indel_nuclease':
        profile = raw.pop('profile')
        if profile == 'explicit':
            raw.pop('tigr_target_sequence'); raw.pop('tigr_window')
        else:
            raw.pop('quantification_window_coordinates')
            raw['nuclease_profile'] = profile
    return {k: _csv_value(k, v) if isinstance(v,str) else v for k,v in raw.items()}


def compile_draft(content, revision, references, protected):
    issues, target_previews, sample_rows, target_rows, input_evidence = [], [], [], [], {}
    def issue(step, field, code, message, severity='ERROR', detail=None):
        issues.append(SetupIssue(step=step,field=field,code=code,message=message,severity=severity,detail=detail))
    def errors(step):
        return any(i.step==step and i.severity=='ERROR' for i in issues)
    def model_issues(exc,step,prefix,fallback):
        if isinstance(exc,ValidationError):
            for e in exc.errors(include_url=False,include_input=False):
                suffix='.'.join(map(str,e['loc']))
                field=prefix+('.'+suffix if suffix else '.'+fallback)
                issue(step,field,'SCHEMA_VALIDATION',e['msg'])
        else:
            text=str(exc); field=prefix+'.'+fallback
            if step=='samples' and 'dpi must' in text:field=prefix+'.dpi'
            if step=='target':
                if any(t in text for t in ('TIGR','target must','target not','multiple physical')):field=prefix+'.tigr_target_sequence'
                elif 'window' in text or 'interval' in text or 'coordinate' in text:field=prefix+'.quantification_window_coordinates'
            issue(step,field,'METADATA_VALIDATION',text)
    if not content.analysis_name.strip():
        issue('samples','analysis_name','REQUIRED','Provide an analysis name.')
    if not content.samples:
        issue('samples','samples','REQUIRED','Add at least one biological sample.')
    for index,row in enumerate(content.samples):
        try: Sample.model_validate({k:_csv_value(k,v) if isinstance(v,str) else v for k,v in row.model_dump().items()})
        except ValueError as exc:model_issues(exc,'samples',f'samples.{index}','sample_name')
    config=Config.model_validate({'schema_version':1,'demux':{'profile':content.library_profile}})
    catalog=load_catalog(bundled_catalog()) if content.library_profile=='qi_hitom_v1' else Catalog([],authoritative=False)
    if content.samples and not errors('samples'):
        try:
            sample_rows=sorted(load_samples(MemoryCSV([r.model_dump() for r in content.samples],'Draft samples'),catalog),key=lambda r:r.barcode_id)
            safety,_=validate_catalog_matching(catalog,config.demux.max_mismatches)
            rules=extraction_rules(config.demux,catalog)
        except ValueError as exc:issue('samples','samples','SAMPLE_METADATA',str(exc))
    if content.analysis_mode is None:
        issue('mode','analysis_mode','REQUIRED','Select Precise Edit or Indel / Nuclease.')
    if not content.targets:
        issue('target','targets','REQUIRED','Add a target definition.')
    if content.analysis_mode=='indel_nuclease' and len(content.targets)!=1:
        issue('target','targets','MULTICOPY_NUCLEASE_UNSUPPORTED','Nuclease setup requires exactly one copy.')
    for index,row in enumerate(content.targets):
        if row.analysis_mode!=content.analysis_mode:
            issue('target',f'targets.{index}','MODE_MISMATCH','Target fields must match the selected analysis mode.');continue
        try:
            values=target_values(row)
            cls=NucleaseTarget if row.analysis_mode=='indel_nuclease' else Target
            cls.model_validate(values)
        except ValueError as exc:
            fallback='tigr_target_sequence' if row.analysis_mode=='indel_nuclease' and row.profile=='tigr_tas_v1' else 'quantification_window_coordinates' if row.analysis_mode=='indel_nuclease' else 'prime_edited_sequence'
            model_issues(exc,'target',f'targets.{index}',fallback)
    if content.targets and not errors('target'):
        try:
            csv_rows=[{k:'' if v is None else v for k,v in target_values(r).items()} for r in content.targets]
            target_rows=sorted(load_targets(MemoryCSV(csv_rows,'Draft targets')),key=lambda t:(t.target_name,t.copy_name))
            if len({t.target_name for t in target_rows})!=1:raise ValueError('MULTI_TARGET_EXECUTION_UNSUPPORTED: one biological target is required')
            if content.analysis_mode=='precise_edit':
                g=geometry(target_rows,min_distinguishing_sites=RoutingPolicy().min_distinguishing_sites,reference_only=True)
                # Preserve backend routing gates: a blocked copy route can still permit target metrics.
                for reason in g['reasons']:
                    code=reason['code']
                    target_error=code in {'NONUNIQUE_REFERENCE_ALIGNMENT','NONUNIQUE_EDIT_ALIGNMENT','PE_GUIDE_REFERENCE_MISMATCH_UNSUPPORTED','PE_GUIDE_ORIENTATION_UNSUPPORTED','NONUNIQUE_SPACER_LOCATION','PE_EXTENSION_LOCATION_UNSUPPORTED'}
                    issue('target','targets',code,'Backend reference geometry: '+code,'ERROR' if target_error else 'WARNING',json.dumps(reason,sort_keys=True))
                for t in target_rows:
                    target_previews.append(TargetPreview(target_name=t.target_name,copy_name=t.copy_name,wt_sequence=t.wt_sequence,intended_sequence=t.prime_edited_sequence,
                        annotation=fields(g['copies'][t.copy_name]),scientific_configuration=fields(scientific_target(t))))
            else:
                t=target_rows[0]
                target_previews.append(TargetPreview(target_name=t.target_name,copy_name=t.copy_name,wt_sequence=t.wt_sequence,intended_sequence=None,
                    annotation=fields(t.window),scientific_configuration=fields(t.scientific_identity['backend_settings']),
                    configuration_notes=['CRISPResso2 2.3.4 qualified backend requirement',
                        'Substitutions retained; current insertion semantics require both anchors in the selected window.',
                        'End exclusions 0/0; single WT reference.',
                        'Ambiguous aligned population must be zero; discarded aligned population must be zero.',
                        'All 58 resolved scientific fields are locked.']))
        except (ValueError,KeyError) as exc:issue('target','targets','TARGET_VALIDATION',str(exc))
    trims=None
    preparation=None
    try:
        parsed=[None if not v.strip() else int(v) for v in (content.trim_r1,content.trim_r2)]
        preparation=PreparationConfig(r1_analysis_trim_5p=parsed[0],r2_analysis_trim_5p=parsed[1])
        if content.input_mode=='run' and sample_rows and not errors('samples'):
            summary={'resolved_config':config.model_dump(),'extraction_profile':{'rules':{k:v.model_dump() for k,v in rules.items()}},'barcode_catalog':{'matching_safety':safety}}
            trims=resolve_trims(summary,preparation)
        elif (parsed[0] is None)!=(parsed[1] is None):raise ValueError('Supply both analysis trim sizes.')
    except ValueError as exc:issue('configuration','trim_r1','PREPARATION_CONFIG',str(exc))
    try:
        if content.input_mode=='run':
            if content.demux is not None:raise ValueError('Raw pool input cannot also select a demux archive.')
            for role in ('r1','r2'):
                ref=getattr(content,role)
                if not ref:issue('samples',role,'REQUIRED','Select '+role.upper()+'.')
            if content.r1 and content.r2:
                r1=references.resolve(content.r1,'fastq');r2=references.resolve(content.r2,'fastq')
                if r1.samefile(r2):raise ValueError('R1 and R2 must be distinct input files.')
                input_evidence={role:references.identity(ref) for role,ref in [('r1',content.r1),('r2',content.r2)]}
                pairs=0
                for pair in paired_fastq(r1,r2):
                    if trims and any(len(r.sequence)<=n for r,n in zip(pair,trims)):raise ValueError('Read length must exceed configured analysis trim.')
                    pairs+=1
                input_evidence['paired_records']=str(pairs)
                if pairs==0:issue('samples','r1','EMPTY_INPUT','The paired FASTQ population is empty.','WARNING')
        else:
            if content.r1 or content.r2:raise ValueError('Verified demux input cannot also select raw R1/R2.')
            if not content.demux:issue('samples','demux','REQUIRED','Select a verified demux archive.')
            else:
                root=references.resolve(content.demux,'demux')
                verified=verify_demux_output(root)
                if sample_rows:_demux_samples(verified,sample_rows)
                if preparation is not None:
                    trims=resolve_trims(verified.summary,preparation)
                    for sample in verified.samples:
                        for pair in paired_fastq(sample.r1,sample.r2):
                            if any(len(record.sequence)<=trim for record,trim in zip(pair,trims)):
                                raise ValueError('Archived read length must exceed configured analysis trim.')
                input_evidence={'demux':references.identity(content.demux)}
    except (OSError,ValueError) as exc:issue('samples','demux' if content.input_mode=='analyze' else 'r1','INPUT_VALIDATION',str(exc))
    output=None
    output_identity=None
    if content.output_root:
        try:
            from pydantic import TypeAdapter
            leaf=TypeAdapter(Identifier).validate_python(content.workspace_name)
            parent=references.resolve(content.output_root,'output_root');destination=owned(parent,leaf)
            if destination.exists():raise ValueError('Output destination already exists; select a new workspace name.')
            reserved=[*protected,*[p for key,p in references.paths.items() if references.entries[key].kind!='output_root']]
            if any(destination==p or p.is_relative_to(destination) or (p.is_dir() and destination.is_relative_to(p)) for p in reserved):
                raise ValueError('Output proposal overlaps protected scientific inputs/workspaces.')
            output=references.label(content.output_root)+' / '+leaf
            output_identity=digest(str(destination))
        except (OSError,ValueError) as exc:issue('configuration','workspace_name','OUTPUT_PROPOSAL',str(exc))
    if sample_rows and target_rows:
        for warning in metadata_warnings(sample_rows,target_rows,config):
            issue('target','targets','BACKEND_METADATA_WARNING',warning,'WARNING')
    preview=None
    if not any(i.severity=='ERROR' for i in issues):
        backend=dict(package_version=__version__,backend_base=BASE,crispresso_required='2.3.4',runtime_digest_required=RUNTIME_DIGEST,
            executable_probed=False,qualification='Expected contract only; resolved execution must be verified in M11B')
        normalized=dict(mode=content.analysis_mode,source_mode=content.input_mode,samples=[r.model_dump() for r in sample_rows],
            targets=[scientific_target(t) for t in target_rows],inputs=input_evidence,
            demux_config=config.model_dump(),preparation=dict(r1_analysis_trim_5p=trims[0],r2_analysis_trim_5p=trims[1]),
            routing_policy=policy_identity(RoutingPolicy()) if content.analysis_mode=='precise_edit' else 'single_copy_identity',statistics='summarize',backend=backend)
        science=digest(normalized)
        nodes=dag(content.input_mode,[s.barcode_id for s in sample_rows],sorted({t.target_name for t in target_rows}))
        stages=[PreviewStage(stage_id=n.stage_id,kind=n.stage_kind,label='Single-copy identity check' if content.analysis_mode=='indel_nuclease' and n.stage_kind=='routing' else n.stage_kind,dependencies=n.dependencies,output_path=n.output_path) for n in nodes]
        preview=PlanPreview(analysis_name=content.analysis_name,analysis_mode=content.analysis_mode,source_mode=content.input_mode,
            sample_count=str(len(sample_rows)),sample_ids=[s.barcode_id for s in sample_rows],samples=fields({s.barcode_id:s.model_dump() for s in sample_rows}),
            inputs=fields(input_evidence),target_name=target_rows[0].target_name,copy_count=str(len(target_rows)),targets=target_previews,
            configuration=fields({k:normalized[k] for k in ('demux_config','preparation','routing_policy','statistics')}),stages=stages,output_proposal=output,
            scientific_identity_sha256=science,plan_identity_sha256=digest(dict(scientific_identity=science,analysis_name=content.analysis_name,output=output_identity)),
            backend_identity=fields(backend),deferred=['Scientific execution','Core executable/runtime verification','Resolved argument and population qualification','Progress / cancel / resume / force','Contrast creation','PE empirical routing qualification'])
    return DraftValidation(revision=revision,draft_digest=digest(content),status='VALID' if preview else 'INVALID',issues=issues,targets=target_previews if not errors('target') else [],preview=preview)
