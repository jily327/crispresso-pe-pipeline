"""Opaque recovery sessions around authoritative, read-only workflow preflight."""
from pathlib import Path
import shutil
import threading
import uuid
from typing import Literal
from pydantic import BaseModel, ConfigDict
from peanalyzer import workflow as w
from peanalyzer.gui.execution import RuntimeSettings
from peanalyzer.gui.models import ErrorDetail, Registration
from peanalyzer.gui.projection import fields
from peanalyzer.gui.recovery_models import RecoveryView, RecoveryStage
from peanalyzer.gui.workspace import safe_registration, registration_labels
from peanalyzer.gui.process_safety import lease_busy
from peanalyzer.workflow_models import Plan, Backend
from peanalyzer.workflow_storage import WorkflowError, load, owned, no_symlinks, sha, digest
from peanalyzer.workflow_recovery import preflight_resume, workspace_identity, options_from_plan

class RecoveryExecution(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True,strict=True)
    intent: Literal['recovery']='recovery'
    job_id: str
    recovery_id: str
    revision: int
    output: str
    runtime: RuntimeSettings
    force: list[str]
    recovery_plan_sha256: str
    workflow_plan: Plan


def inspect(root,runtime,force=(),*,check_active=True):
    """No executable probe, writes, invalidation or resume. Fail closed by default."""
    root=no_symlinks(root)
    before=workspace_identity(root)
    old=load(owned(root,'workflow/plan.json'),Plan)
    if old.output!=str(root):raise WorkflowError('INVALID_WORKSPACE','Workspace relocation is unsupported')
    from peanalyzer.workflow_integrity import authenticate, RECEIPT
    # Legacy completed results remain subject to the portable final verifier.
    # Recovery never retroactively authenticates their mutable metadata.
    if owned(root,RECEIPT).exists():authenticate(root,old)
    if owned(root,'workflow_manifest.json').exists():
        try:
            w.verify_workflow_output(root)
        except (ValueError,OSError):
            if not owned(root,RECEIPT).exists():
                raise WorkflowError('TAMPERED_COMPLETION_MARKER','Unanchored completion cannot be reconciled')
        else:return old,None,'COMPLETED'
    if check_active and lease_busy():raise WorkflowError('WORKER_BUSY','An active scientific supervisor holds the host lease')
    lock=no_symlinks(root.with_name('.'+root.name+'.m7-lock'))
    if lock.exists():raise WorkflowError('WORKFLOW_LOCKED','Existing invocation lock requires ownership review; it is never removed by recovery')
    if runtime is None:raise WorkflowError('RUN_UNAVAILABLE','A qualified runtime is required for recovery')
    w.verify_inputs(old.inputs)
    if old.mode=='analyze':
        w._demux_samples(w.verify_demux_output(Path(old.normalized_options['external_demux'])),old.samples)
    current=w.software_identity()
    if current!=old.software_identity and 'all' not in force:
        raise WorkflowError('SOFTWARE_CHANGED','Stored software differs. Only an explicit full rebuild can replace every stage identity')
    executable=shutil.which(runtime.crispresso)
    if not executable:raise WorkflowError('BACKEND_UNAVAILABLE','Configured executable is unavailable; no probe was executed')
    executable=no_symlinks(executable)
    backend=Backend(executable=str(executable),executable_sha256=sha(executable),version='2.3.4',runtime_digest=runtime.runtime_digest)
    plan=old.model_copy(update={'software_identity':current,'backend_identity':backend})
    preflight=preflight_resume(old,plan,force)
    if before!=preflight['workspace_identity']:raise WorkflowError('RECOVERY_PLAN_CHANGED','Workspace changed during inspection')
    return plan,preflight,'RESUMABLE_WITH_FORCE' if force else 'RESUMABLE'


def run_recovery(spec,emit):
    # Our inherited host lease is expected; the M7 workspace lock must be absent.
    plan,preflight,state=inspect(Path(spec.output),spec.runtime,spec.force,check_active=False)
    if preflight is None or digest(preflight)!=spec.recovery_plan_sha256 or plan!=spec.workflow_plan:
        raise WorkflowError('RECOVERY_PLAN_CHANGED','Recovery changed after confirmation; inspect again')
    emit(dict(status='WORKER_READY'))
    w.resume_workflow(**options_from_plan(plan,crispresso=spec.runtime.crispresso,runtime_digest=spec.runtime.runtime_digest),
        force=spec.force,expected_plan=plan,expected_recovery_identity=spec.recovery_plan_sha256,
        argv=['gui-recovery',spec.job_id,'--recovery-plan',spec.recovery_plan_sha256],observer=emit)
    w.verify_workflow_output(spec.output);emit(dict(status='VERIFIED_SUCCESS'))


class RecoveryStore:
    def __init__(self,paths,jobs,workspaces):
        self.registrations={uuid.uuid4().hex:safe_registration(p) for p in paths}
        self.sessions={};self.lock=threading.RLock();self.jobs=jobs;self.workspaces=workspaces

    def catalog(self):
        labels=registration_labels([(None,p) for p in self.registrations.values()])
        return [Registration(registration_id=k,label=label) for k,(label,_) in zip(self.registrations,labels)]

    def from_job(self,key):
        with self.jobs.lock:
            job=self.jobs._job(key)
            if job.view.state not in {'FAILED','CANCELLED'}:raise WorkflowError('RECOVERY_UNAVAILABLE','Only failed/cancelled jobs can be inspected here')
            import json
            path=safe_registration(json.loads(job.payload)['output'])
        with self.lock:
            key=uuid.uuid4().hex;self.registrations[key]=path
            return self.open(key)

    def open(self,key):
        with self.lock:
            if key not in self.registrations:raise WorkflowError('UNKNOWN_REGISTRATION','Select a registered recovery workspace')
            session=uuid.uuid4().hex;self.sessions[session]=dict(root=self.registrations[key],revision=0,force=[],accepted=False)
            return self.preview(session,0,[])

    def preview(self,key,revision,force):
        with self.lock:
            item=self._session(key,revision)
            if item['accepted']:raise WorkflowError('RECOVERY_LOCKED','This preview belongs to an accepted job; inspect again')
            force=sorted(set(force))
            if set(force)-set(w.FORCE_FAMILIES):raise WorkflowError('INVALID_FORCE','Unknown backend force family')
            item['force']=force;item['revision']+=1
            view=self._view(key,item)
            item['view']=view
            return view.model_copy(deep=True)

    def _session(self,key,revision):
        if key not in self.sessions:raise WorkflowError('RECOVERY_NOT_FOUND','Unknown recovery session')
        item=self.sessions[key]
        if revision!=item['revision']:raise WorkflowError('STALE_RECOVERY_REVISION','Inspect the current recovery revision')
        return item

    def _view(self,key,item):
        root=item['root'];force=item['force'];families=list(w.FORCE_FAMILIES)
        view=RecoveryView(recovery_id=key,revision=item['revision'],workspace_label=root.name,
            classification='INVALID_WORKSPACE',force_families=families,selected_force=force)
        try:
            old=load(owned(root,'workflow/plan.json'),Plan)
            view.analysis_mode=old.targets[0].analysis_mode
            view.scientific_identity_sha256=digest(dict(samples=old.samples,targets=[w.scientific_target(t) for t in old.targets],options=old.normalized_options,inputs={k:v.model_dump() for k,v in old.inputs.items()}))
            view.workflow_identity_sha256=digest(old)
            view.software=fields(old.software_identity.model_dump());view.backend=fields(old.backend_identity.model_dump())
            if old.mode=='analyze':view.force_families.remove('demux')
            view.stages=[RecoveryStage(stage_id=n.stage_id,stage_kind=n.stage_kind,action='BLOCKED',output_path=n.output_path,reason_codes=[]) for n in old.nodes]
            plan,pf,state=inspect(root,self.jobs.runtime,force)
            view.classification=state
            if pf is not None:
                view.recovery_plan_sha256=digest(pf);view.stages=[RecoveryStage(**s) for s in pf['stages']]
                view.closure=pf['closure'];view.removal_paths=pf['removal_paths'];view.executable=self.jobs.available
                view.software=fields(plan.software_identity.model_dump());view.backend=fields(plan.backend_identity.model_dump())
                item['plan']=plan
            if state=='COMPLETED':view.force_families=[];view.selected_force=[]
        except (ValueError,OSError) as exc:
            code=getattr(exc,'code','INVALID_WORKSPACE')
            classification={'WORKER_BUSY':'ACTIVE','WORKFLOW_LOCKED':'ACTIVE','SOURCE_CHANGED':'STALE_INPUT',
                'SOFTWARE_CHANGED':'SOFTWARE_CHANGED','RUN_UNAVAILABLE':'UNSUPPORTED','BACKEND_UNAVAILABLE':'UNSUPPORTED',
                'ORPHANED_STAGE_OUTPUT':'RESUMABLE_WITH_FORCE','STALE_STAGE_IDENTITY':'RESUMABLE_WITH_FORCE',
                'CORRUPTED_STAGE_OUTPUT':'TAMPERED','SNAPSHOT_CORRUPTED':'TAMPERED','UNSAFE_PATH':'TAMPERED',
                'TAMPERED_STAGE_MANIFEST':'TAMPERED','FOREIGN_CONTENT_PRESENT':'TAMPERED',
                'TAMPERED_WORKFLOW_PLAN':'TAMPERED','TAMPERED_COMPLETION_MARKER':'TAMPERED',
                'TAMPERED_RECOVERY_INTEGRITY':'TAMPERED','UNSAFE_RECOVERY_KEY':'TAMPERED',
                'UNANCHORED_RECOVERY_OWNERSHIP':'UNSUPPORTED'}.get(code,'INVALID_WORKSPACE')
            view.classification=classification
            view.reasons=[ErrorDetail(code=code,message='Recovery requires inspection or a different explicit choice.',detail=str(exc),stage_id=getattr(exc,'stage_id',None))]
        return view

    def execute(self,key,request):
        # Consistent lock order with new Run: lifecycle first, then recovery state.
        with self.jobs.lock,self.lock:
            item=self._session(key,request.revision)
            if item['accepted']:raise WorkflowError('RECOVERY_LOCKED','Recovery was already accepted')
            if not self.jobs.available:raise WorkflowError('RUN_UNAVAILABLE','Scientific runtime unavailable')
            if self.jobs.active is not None or lease_busy():raise WorkflowError('WORKER_BUSY','Another scientific supervisor is active')
            prior=item['view'];fresh=self._view(key,item)
            if not prior.executable or not fresh.executable or fresh.recovery_plan_sha256!=request.recovery_plan_sha256 or prior.recovery_plan_sha256!=request.recovery_plan_sha256:
                raise WorkflowError('RECOVERY_PLAN_CHANGED','Recovery preview is stale or unsafe; inspect again before confirmation')
            result=self.jobs.submit_recovery(key,item,fresh)
            item['accepted']=True
            return result

    def open_results(self,key):
        with self.lock:
            if key not in self.sessions:raise WorkflowError('RECOVERY_NOT_FOUND','Unknown recovery session')
            item=self.sessions[key];view=self._view(key,item)
            if view.classification!='COMPLETED':raise WorkflowError('INCOMPLETE_WORKSPACE','Open Results requires verified completion')
            return self.workspaces.register_completed(item['root'].name,item['root'])
