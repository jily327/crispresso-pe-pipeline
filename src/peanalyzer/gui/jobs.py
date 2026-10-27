"""One leased Linux supervisor, immutable accepted jobs, verified publication."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import uuid
from peanalyzer.gui.execution import ExecutionSpec, check_destination
from peanalyzer.gui.job_models import JobView, JobStage, JobEvent, JobEvents
from peanalyzer.gui.models import ErrorDetail, FieldValue
from peanalyzer.gui.workspace import ViewerError
from peanalyzer.workflow_storage import canonical, owned

TERMINAL={'CANCELLED','FAILED','COMPLETED'}


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def worker_command(events_fd):
    return [sys.executable,'-m','peanalyzer.gui.worker','--events-fd',str(events_fd)]


def subreaper():
    # Reap only adopted descendants in our own worker process group.
    if sys.platform.startswith('linux'):
        import ctypes
        if ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0):
            raise OSError('Cannot supervise descendant reaping')


def signal_group(pid,sig):
    try:os.killpg(pid,sig)
    except ProcessLookupError:pass


def group_alive(pid):
    try:os.killpg(pid,0)
    except ProcessLookupError:return False
    return True


def reap_group(pid):
    if not sys.platform.startswith('linux'):return
    while True:
        try:
            child,_=os.waitpid(-pid,os.WNOHANG)
            if not child:break
        except ChildProcessError:break


@dataclass
class Job:
    view: JobView
    payload: bytes
    started: float = field(default_factory=time.monotonic)
    ended: float | None = None
    events: list = field(default_factory=list)
    cancel: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None
    process: object = None
    finishing: bool = False
    lease_fd: int | None = None


class JobStore:
    def __init__(self,drafts,workspaces,runtime=None):
        self.drafts=drafts;self.workspaces=workspaces;self.runtime=runtime
        self.jobs={};self.active=None;self.lock=threading.RLock();self.closing=False
        self.grace_seconds=5.0

    @property
    def available(self):
        from peanalyzer.gui.process_safety import supported
        return self.runtime is not None and supported()

    def _job(self,key):
        if key not in self.jobs:raise ViewerError('JOB_NOT_FOUND','The job is not owned by this application session.')
        return self.jobs[key]

    def _event(self,job,status,**values):
        event=JobEvent(sequence=len(job.events)+1,timestamp=timestamp(),state=job.view.state,status=status,**values)
        job.events.append(event);job.view.latest_sequence=event.sequence

    def get(self,key):
        with self.lock:
            job=self._job(key);view=job.view.model_copy(deep=True)
            view.elapsed_seconds=round((job.ended or time.monotonic())-job.started,1)
            return view

    def catalog(self):
        with self.lock:return [self.get(key) for key in self.jobs]

    def events(self,key,after,limit):
        with self.lock:
            rows=self._job(key).events
            page=rows[after:after+limit]
            return JobEvents(items=[e.model_copy(deep=True) for e in page],
                next_sequence=page[-1].sequence if page else after,has_more=after+len(page)<len(rows))

    def submit(self,request):
        with self.lock,self.drafts.lock:
            if not self.available:raise ViewerError('RUN_UNAVAILABLE','A supported local scientific runtime must be configured by the launcher.')
            if self.closing:raise ViewerError('SERVER_STOPPING','The application is stopping.')
            if self.active is not None:raise ViewerError('WORKER_BUSY','Another analysis is active. No job was queued.')
            drafts=self.drafts
            drafts.editable(request.draft_id)
            view=drafts.check(request.draft_id,request.revision)
            if not view.validation or view.validation.status!='VALID':raise ViewerError('DRAFT_NOT_VALID','Validate and review this draft first.')
            reviewed=drafts.preview(request.draft_id,request.revision)
            for key,code in [('plan_identity_sha256','PLAN_IDENTITY_CHANGED'),('scientific_identity_sha256','SCIENTIFIC_IDENTITY_CHANGED')]:
                if getattr(reviewed,key)!=getattr(request,key):raise ViewerError(code,'The submitted identity differs from Review.')
            validation=drafts.validate(request.draft_id,request.revision)
            if validation.status!='VALID':raise ViewerError('DRAFT_NOT_VALID','The draft no longer passes authoritative validation.')
            preview=validation.preview
            for key,code in [('plan_identity_sha256','PLAN_IDENTITY_CHANGED'),('scientific_identity_sha256','SCIENTIFIC_IDENTITY_CHANGED')]:
                if getattr(reviewed,key)!=getattr(preview,key):raise ViewerError(code,'The reviewed plan changed. Review again before Run.')
            if not view.content.output_root or not preview.output_proposal:
                raise ViewerError('OUTPUT_REQUIRED','Select and validate a new output destination before Run.')
            parent=drafts.references.resolve(view.content.output_root,'output_root')
            output=owned(parent,view.content.workspace_name)
            job_id=uuid.uuid4().hex
            spec=ExecutionSpec(job_id=job_id,revision=view.revision,content=view.content,
                references=[dict(file_id=k,label=e.label,kind=e.kind,path=str(drafts.references.paths[k]))
                    for k,e in drafts.references.entries.items()],protected=[str(p) for p in drafts.protected],
                signature=drafts.identities[view.draft_id],compiled=validation._compiled,
                plan_identity_sha256=preview.plan_identity_sha256,scientific_identity_sha256=preview.scientific_identity_sha256,
                output=str(output),output_parent_identity=[parent.stat().st_dev,parent.stat().st_ino],runtime=self.runtime)
            check_destination(spec)
            payload=canonical(spec.model_dump()).encode();checksum=hashlib.sha256(payload).hexdigest()
            summary=JobView(job_id=job_id,draft_id=view.draft_id,revision=view.revision,state='STARTING',
                analysis_name=preview.analysis_name,analysis_mode=preview.analysis_mode,target_name=preview.target_name,
                output_proposal=preview.output_proposal,plan_identity_sha256=preview.plan_identity_sha256,
                scientific_identity_sha256=preview.scientific_identity_sha256,execution_spec_sha256=checksum,
                input_metadata=[FieldValue(name=name,value=hashlib.sha256(value.encode()).hexdigest())
                    for name,value in spec.compiled['files'].items()],warnings=[i for i in validation.issues if i.severity=='WARNING'],
                stages=[JobStage(**s.model_dump()) for s in preview.stages],total_stages=len(preview.stages),started_at=timestamp())
            from peanalyzer.gui.process_safety import acquire_lease
            job=Job(summary,payload,lease_fd=acquire_lease())
            self.jobs[job_id]=job;self.active=job_id;drafts.frozen[view.draft_id]=job_id
            drafts.protected=(*drafts.protected,output)
            self._event(job,'ACCEPTED')
            job.thread=threading.Thread(target=self._supervise,args=(job,),name='peanalyzer-job-'+job_id,daemon=True)
            try:job.thread.start()
            except Exception:
                os.close(job.lease_fd);job.lease_fd=None
                self.jobs.pop(job_id);self.active=None;drafts.frozen.pop(view.draft_id,None)
                raise
            return self.get(job_id)

    def submit_recovery(self,key,item,preview):
        from peanalyzer.gui.recovery import RecoveryExecution
        from peanalyzer.gui.process_safety import acquire_lease
        if self.closing:raise ViewerError('SERVER_STOPPING','The application is stopping')
        if self.active is not None:raise ViewerError('WORKER_BUSY','Another analysis is active')
        job_id=uuid.uuid4().hex
        plan=item['plan']
        spec=RecoveryExecution(job_id=job_id,recovery_id=key,revision=item['revision'],output=str(item['root']),
            runtime=self.runtime,force=item['force'],recovery_plan_sha256=preview.recovery_plan_sha256,workflow_plan=plan)
        payload=canonical(spec.model_dump()).encode()
        summary=JobView(job_id=job_id,draft_id=key,revision=item['revision'],state='STARTING',
            analysis_name=plan.normalized_options['title'],analysis_mode=plan.targets[0].analysis_mode,
            target_name=plan.expected_targets[0],output_proposal=item['root'].name,
            plan_identity_sha256=preview.recovery_plan_sha256,scientific_identity_sha256=preview.scientific_identity_sha256,
            execution_spec_sha256=hashlib.sha256(payload).hexdigest(),input_metadata=[],warnings=[],
            stages=[JobStage(stage_id=n.stage_id,kind=n.stage_kind,label=n.stage_kind,dependencies=n.dependencies,output_path=n.output_path) for n in plan.nodes],
            total_stages=len(plan.nodes),started_at=timestamp())
        job=Job(summary,payload,lease_fd=acquire_lease())
        self.jobs[job_id]=job;self.active=job_id;self._event(job,'ACCEPTED')
        job.thread=threading.Thread(target=self._supervise,args=(job,),name='peanalyzer-job-'+job_id,daemon=True)
        try:job.thread.start()
        except Exception:
            os.close(job.lease_fd);job.lease_fd=None
            self.jobs.pop(job_id);self.active=None
            raise
        return self.get(job_id)

    def cancel(self,key):
        with self.lock:
            job=self._job(key)
            if job.view.state in TERMINAL or job.finishing:return self.get(key)
            if not job.cancel.is_set():
                job.cancel.set();job.view.state='CANCELLING';job.view.cancellable=False
                self._event(job,'CANCEL_REQUESTED')
            return self.get(key)

    def _observe(self,job,event):
        with self.lock:
            status=event.get('status');stage_id=event.get('stage_id')
            stage=next((s for s in job.view.stages if s.stage_id==stage_id),None)
            if status=='WORKER_READY' and not job.cancel.is_set():job.view.state='RUNNING'
            if status=='CONTAINMENT_ERROR':
                job.view.state='FAILED';job.view.cancellable=False
                job.view.error=ErrorDetail(code='CANCELLATION_INCOMPLETE',message='Scientific process containment is incomplete.',
                    detail=event.get('message','The host worker lease remains held.'))
            if stage and status in {'RUNNING','COMPLETED','SKIPPED_SCIENTIFIC_GATE','REUSED','FAILED'}:
                stage.status=status;stage.reason_codes=list(event.get('reason_codes') or [])
                job.view.current_stage_id=stage_id
                job.view.finished_stages=sum(s.status in {'COMPLETED','SKIPPED_SCIENTIFIC_GATE','REUSED'} for s in job.view.stages)
            if status=='FINAL_VALIDATION':job.view.current_stage_id=None
            self._event(job,str(status),stage_id=stage_id,stage_kind=event.get('stage_kind'),
                reason_codes=event.get('reason_codes') or [],code=event.get('code'))

    def _supervise(self,job):
        process=None;reader=None;drainer=None;read_fd=None;write_fd=None
        received=[];logs=bytearray();failure=None;verified=False
        def hardened():return any(e.get('status')=='SUPERVISOR_READY' for e in received)
        def confirmed():return any(e.get('status')=='CONTAINMENT_CONFIRMED' for e in received)
        try:
            with self.lock:
                if job.cancel.is_set():return
                subreaper()
                read_fd,write_fd=os.pipe()
                from peanalyzer.gui.process_safety import process_identity
                env=dict(os.environ,PEANALYZER_SUPERVISOR_PARENT=str(os.getpid()),
                    PEANALYZER_SUPERVISOR_PARENT_START=str(process_identity(os.getpid())['start_ticks']))
                process=subprocess.Popen(worker_command(write_fd),stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,pass_fds=(write_fd,job.lease_fd),start_new_session=True,env=env)
                job.process=process
                os.close(write_fd);write_fd=None
            def read_events():
                with os.fdopen(read_fd,'r') as stream:
                    for line in stream:
                        try:
                            event=json.loads(line);received.append(event);self._observe(job,event)
                        except (ValueError,TypeError):pass
            def drain():
                while chunk:=process.stdout.read(4096):
                    logs.extend(chunk)
                    if len(logs)>16384:del logs[:-16384]
                process.stdout.close()
            reader=threading.Thread(target=read_events,daemon=True);reader.start()
            drainer=threading.Thread(target=drain,daemon=True);drainer.start()
            envelope=canonical(dict(spec=json.loads(job.payload),sha256=job.view.execution_spec_sha256)).encode()
            try:process.stdin.write(envelope);process.stdin.close()
            except BrokenPipeError:pass
            deadline=None
            while process.poll() is None:
                if job.cancel.is_set() and hardened():
                    if deadline is None:process.send_signal(signal.SIGTERM);deadline=time.monotonic()+self.grace_seconds
                job.cancel.wait(.05) if not job.cancel.is_set() else time.sleep(.05)
            process.wait()
            # A leader can exit before its backend children. Do not release the slot
            # or publish completion until every member of its process group is gone.
            if not hardened():
                signal_group(process.pid,signal.SIGTERM)
                deadline=time.monotonic()+self.grace_seconds
                while group_alive(process.pid):
                    reap_group(process.pid)
                    if time.monotonic()>=deadline:signal_group(process.pid,signal.SIGKILL)
                    if not group_alive(process.pid):break
                    time.sleep(.02)
                reap_group(process.pid)
            reader.join(timeout=1);drainer.join(timeout=1)
            if not confirmed():
                raise ViewerError('CANCELLATION_INCOMPLETE','Supervisor exited without positive containment acknowledgement; host lease retained.')
            verified=process.returncode==0 and any(e.get('status')=='VERIFIED_SUCCESS' for e in received)
            errors=[e for e in received if e.get('status')=='WORKER_ERROR']
            if errors:
                item=errors[-1]
                failure=ErrorDetail(code=item.get('code','WORKER_FAILED'),message='The scientific workflow stopped.',
                    detail=item.get('message',''),stage_id=item.get('stage_id') or job.view.current_stage_id)
            elif not verified:
                failure=ErrorDetail(code='WORKER_EXITED',message='The worker did not produce verified completion.',
                    detail=logs.decode('utf-8','replace') or f'Worker exit code: {process.returncode}')
            with self.lock:
                if job.cancel.is_set():return
                job.finishing=True;job.view.cancellable=False
                self._event(job,'VIEWER_VERIFICATION')
            if verified:
                payload=json.loads(job.payload)
                opened=self.workspaces.register_completed(job.view.analysis_name,Path(payload['output']))
                with self.lock:job.view.workspace_id=opened.workspace_id
        except Exception as exc:
            failure=ErrorDetail(code=getattr(exc,'code','WORKER_FAILED'),message='Analysis could not be completed and verified.',
                detail=str(exc),stage_id=getattr(exc,'stage_id',None))
        finally:
            if write_fd is not None:os.close(write_fd)
            if process is not None:
                if process.poll() is None:
                    if any(e.get('status')=='SUPERVISOR_READY' for e in received):
                        process.send_signal(signal.SIGTERM)
                        process.wait()  # Supervisor retains lease until owned descendants are reaped.
                    else:
                        signal_group(process.pid,signal.SIGKILL);process.wait()
                # Never signal a hardened supervisor's numeric PGID after reaping.
                if not hardened():
                    signal_group(process.pid,signal.SIGKILL)
                    while group_alive(process.pid):
                        reap_group(process.pid)
                        if group_alive(process.pid):time.sleep(.02)
                    reap_group(process.pid)
                if process.stdin and not process.stdin.closed:process.stdin.close()
                if reader:reader.join(timeout=1)
                if drainer:drainer.join(timeout=1)
            if read_fd is not None and reader is None:os.close(read_fd)
            contained=process is None or (process.poll() is not None and confirmed())
            if job.lease_fd is not None and contained:
                os.close(job.lease_fd);job.lease_fd=None
            with self.lock:
                if not contained:
                    job.view.state='FAILED';job.view.workspace_id=None
                    job.view.error=ErrorDetail(code='CANCELLATION_INCOMPLETE',message='Scientific process containment could not be confirmed.',
                        detail='The host worker lease remains held; supervisor exit is not proof of cleanup.')
                elif job.cancel.is_set():
                    job.view.state='CANCELLED';job.view.workspace_id=None;job.view.error=None
                    for stage in job.view.stages:
                        if stage.stage_id==job.view.current_stage_id and stage.status in {'RUNNING','FAILED'}:stage.status='CANCELLED'
                elif failure is not None or not job.view.workspace_id:
                    job.view.state='FAILED';job.view.error=failure or ErrorDetail(code='WORKER_FAILED',message='No verified result.',detail='')
                else:job.view.state='COMPLETED'
                job.view.cancellable=False;job.ended=time.monotonic();job.view.ended_at=timestamp()
                self._event(job,job.view.state,code=job.view.error.code if job.view.error else None)
                if contained:self.active=None

    def close(self):
        with self.lock:
            self.closing=True
            active=self.jobs.get(self.active)
            if active:self.cancel(active.view.job_id)
        if active and active.thread:active.thread.join(self.grace_seconds+15)
