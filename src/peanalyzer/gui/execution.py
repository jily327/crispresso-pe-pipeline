"""Bind validated GUI compiler output to existing M7 inputs and identities."""
import hashlib
from pathlib import Path
from pydantic import BaseModel, ConfigDict
from peanalyzer.gui.setup_models import DraftContent, SetupFile
from peanalyzer.gui.drafts import SetupReferences
from peanalyzer.gui.setup_validation import compile_draft
from peanalyzer.metrics.production import RUNTIME_DIGEST
from peanalyzer.workflow import scientific_target
from peanalyzer.workflow_storage import WorkflowError, no_symlinks, owned, sha


class RuntimeSettings(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True,strict=True)
    crispresso: str = 'CRISPResso'
    runtime_digest: str = RUNTIME_DIGEST


class ExecutionSpec(BaseModel):
    """Private transport from supervisor to its fixed worker, never an HTTP input."""
    model_config=ConfigDict(extra='forbid',frozen=True,strict=True)
    job_id: str
    revision: int
    content: DraftContent
    references: list[dict[str,str]]
    protected: list[str]
    signature: dict
    compiled: dict
    plan_identity_sha256: str
    scientific_identity_sha256: str
    output: str
    output_parent_identity: list[int]
    runtime: RuntimeSettings


def metadata_hashes(files):
    return {name:hashlib.sha256(value.encode('utf-8')).hexdigest() for name,value in files.items()}


def restore_references(spec):
    references=SetupReferences()
    for item in spec.references:
        key=item['file_id']
        references.paths[key]=no_symlinks(item['path'])
        references.entries[key]=SetupFile(file_id=key,label=item['label'],kind=item['kind'])
    return references


def check_destination(spec):
    root=no_symlinks(spec.output)
    stat=root.parent.stat()
    if [stat.st_dev,stat.st_ino] != spec.output_parent_identity:
        raise WorkflowError('OUTPUT_CHANGED','The selected output parent changed.')
    if root.exists():
        raise WorkflowError('OUTPUT_CHANGED','The selected output destination now exists; new execution only.')
    lock=no_symlinks(root.with_name('.'+root.name+'.m7-lock'))
    if lock.exists():raise WorkflowError('WORKFLOW_LOCKED','The selected destination has an existing invocation lock.')
    return root


def revalidate_execution(spec):
    """No writes/probes: close acceptance-to-worker input and destination races."""
    check_destination(spec)
    refs=restore_references(spec)
    try:
        before=refs.signature(spec.content)
    except (ValueError,OSError) as exc:
        raise WorkflowError('INPUT_CHANGED',str(exc)) from exc
    if before!=spec.signature:raise WorkflowError('INPUT_CHANGED','Accepted input identity changed before execution.')
    result=compile_draft(spec.content,spec.revision,refs,[Path(p) for p in spec.protected])
    if result.status!='VALID':
        raise WorkflowError('DRAFT_NOT_VALID','; '.join(i.message for i in result.issues if i.severity=='ERROR'))
    if result._compiled!=spec.compiled or result.preview.scientific_identity_sha256!=spec.scientific_identity_sha256:
        raise WorkflowError('SCIENTIFIC_IDENTITY_CHANGED','The accepted compiler output changed.')
    if result.preview.plan_identity_sha256!=spec.plan_identity_sha256:
        raise WorkflowError('PLAN_IDENTITY_CHANGED','The accepted plan changed.')
    if refs.signature(spec.content)!=before:raise WorkflowError('INPUT_CHANGED','Inputs changed during worker validation.')
    check_destination(spec)
    return refs


def materialize(spec,refs):
    """Durable original metadata plus M7 snapshots; never disposable temp inputs."""
    root=check_destination(spec)
    library=owned(root.parent,f'.{root.name}.gui-inputs-{spec.job_id}')
    library.mkdir(mode=0o700)
    files=spec.compiled['files']
    for name,value in files.items():
        if name not in {'samples.csv','targets.csv','config.json','barcodes.csv'}:
            raise WorkflowError('INVALID_EXECUTION_SPEC','Unknown compiler metadata role')
        path=owned(library,name)
        with path.open('xb') as stream:stream.write(value.encode('utf-8'))
        if sha(path)!=metadata_hashes(files)[name]:raise WorkflowError('INPUT_CHANGED','Materialized metadata differs')
        path.chmod(0o444)
    science=spec.compiled['science']
    options=dict(mode=science['source_mode'],samples=library/'samples.csv',targets=library/'targets.csv',
        config=library/'config.json',barcodes=library/'barcodes.csv',output=root,
        crispresso=spec.runtime.crispresso,runtime_digest=spec.runtime.runtime_digest,
        title=spec.content.analysis_name,analysis_r1_trim_5p=science['preparation']['r1_analysis_trim_5p'],
        analysis_r2_trim_5p=science['preparation']['r2_analysis_trim_5p'])
    if science['source_mode']=='run':options.update(r1=refs.resolve(spec.content.r1,'fastq'),r2=refs.resolve(spec.content.r2,'fastq'))
    else:options['demux_root']=refs.resolve(spec.content.demux,'demux')
    return options


def bind_plan(spec,plan):
    """Compare authoritative M7 normalization with the SAME setup compilation."""
    science=spec.compiled['science'];options=plan.normalized_options
    actual=dict(mode=plan.targets[0].analysis_mode,source_mode=plan.mode,samples=plan.samples,
        targets=[scientific_target(t) for t in plan.targets],demux_config=options['demux_config'],
        preparation=options['preparation'],statistics=options['statistics_mode'],
        routing_policy=options['routing_policy_identity'] if science['mode']=='precise_edit' else 'single_copy_identity')
    if any(actual[key]!=science[key] for key in actual):
        raise WorkflowError('SCIENTIFIC_IDENTITY_CHANGED','M7 normalization differs from the accepted setup compiler.')
    if plan.output!=spec.output:raise WorkflowError('OUTPUT_CHANGED','M7 output differs from the accepted destination.')
    hashes=metadata_hashes(spec.compiled['files'])
    for role,name in [('samples','samples.csv'),('targets','targets.csv'),('config','config.json'),('barcodes','barcodes.csv')]:
        if plan.inputs[role].sha256!=hashes[name]:raise WorkflowError('INPUT_CHANGED','Metadata identity changed: '+role)
    if set(plan.inputs)-{'samples','targets','config','barcodes','r1','r2'} and plan.mode=='run':
        raise WorkflowError('SCIENTIFIC_IDENTITY_CHANGED','Unexpected execution input role')
    if plan.mode=='run':
        for role in ('r1','r2'):
            item=plan.inputs[role];expected=science['inputs'][role]
            if item.sha256!=expected['sha256'] or str(item.size_bytes)!=expected['size_bytes']:
                raise WorkflowError('INPUT_CHANGED','Raw FASTQ identity changed: '+role)
    if 'contrasts' in plan.inputs or 'policies' in plan.inputs:
        raise WorkflowError('SCIENTIFIC_IDENTITY_CHANGED','Unreviewed contrasts/policies are not allowed.')
    if plan.backend_identity.runtime_digest!=spec.runtime.runtime_digest:
        raise WorkflowError('SCIENTIFIC_IDENTITY_CHANGED','Backend runtime identity changed.')
    check_destination(spec)
