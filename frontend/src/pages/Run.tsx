import { useEffect, useRef, useState } from 'react';
import { api, ViewerFailure } from '../api/client';
import { Fields, Table } from '../components/Common';
import type {RecoveryView} from '../models/recovery';
import type { JobEvent, JobEvents, JobView } from '../models/jobs';

export function Run({jobId,onOpen,onRecovery}:{jobId:string,onOpen:(id:string)=>Promise<void>,onRecovery?:(view:RecoveryView)=>void}) {
  const [job,setJob]=useState<JobView|null>(null),[events,setEvents]=useState<JobEvent[]>([]),[error,setError]=useState('');
  const [confirm,setConfirm]=useState(false),[busy,setBusy]=useState(false);
  const dialog=useRef<HTMLDialogElement>(null),cancelButton=useRef<HTMLButtonElement>(null),heading=useRef<HTMLHeadingElement>(null);
  useEffect(()=>{heading.current?.focus()},[jobId]);
  useEffect(()=>{if(confirm)dialog.current?.showModal();else dialog.current?.close()},[confirm]);
  useEffect(()=>{
    let active=true,cursor=0;let timer:ReturnType<typeof setTimeout>;setJob(null);setEvents([]);setError('');
    async function poll(){try{
      const value=await api<JobView>(`jobs/${jobId}`);if(!active)return;setJob(value);
      let page:JobEvents;
      do {page=await api<JobEvents>(`jobs/${jobId}/events?after=${cursor}`);if(!active)return;
        cursor=page.next_sequence;setEvents(previous=>[...previous,...page.items]);}while(page.has_more);
      setError('');
    }catch(e){if(active)setError(e instanceof ViewerFailure?`${e.detail.code}: ${e.detail.message} ${e.detail.detail}`:String(e))}
    finally{if(active)timer=setTimeout(poll,1000)}}
    void poll();return()=>{active=false;clearTimeout(timer)};
  },[jobId]);
  async function cancel(){setBusy(true);setConfirm(false);try{setJob(await api<JobView>(`jobs/${jobId}/cancel`,{}));setError('')}catch(e){setError(String(e))}finally{setBusy(false);cancelButton.current?.focus()}}
  return <main id="run-main" className="setup"><p className="eyebrow">RUN ANALYSIS</p><h1 ref={heading} tabIndex={-1}>{job?.analysis_name||'Connecting to analysis'}</h1>
    {error&&<p role="alert" className="error-panel">{error}</p>}
    {job&&<><p>Target {job.target_name} · {job.analysis_mode==='precise_edit'?'Precise Edit':'Indel / Nuclease'}</p>
      <p role="status" aria-live="polite"><strong>{job.state}</strong> · {job.finished_stages} / {job.total_stages} stages finished · Elapsed {job.elapsed_seconds} seconds</p>
      <p>Current stage: {job.current_stage_id||'No scientific stage active'}</p><p>Output: {job.output_proposal}</p>
      <dl className="identities"><dt>Job ID</dt><dd>{job.job_id}</dd><dt>Scientific identity SHA-256</dt><dd>{job.scientific_identity_sha256}</dd><dt>Plan identity SHA-256</dt><dd>{job.plan_identity_sha256}</dd><dt>Accepted execution specification SHA-256</dt><dd>{job.execution_spec_sha256}</dd></dl>
      {job.warnings.length>0&&<section aria-label="Accepted setup warnings"><h2>Setup warnings</h2><ul>{job.warnings.map((w,i)=><li key={i}>{w.code}: {w.message}</li>)}</ul></section>}
      <Table caption="Authoritative stage progress" headers={['Stage','Status','Backend reasons']}>{job.stages.map(s=><tr key={s.stage_id}><th scope="row">{s.stage_id} · {s.label}</th><td>{s.status}</td><td>{s.reason_codes.join(', ')||'None'}</td></tr>)}</Table>
      <p>Stage counts show discrete completion, not an estimate of time remaining.</p>
      {job.cancellable&&<button ref={cancelButton} disabled={busy} onClick={()=>setConfirm(true)}>Cancel analysis</button>}
      {job.state==='CANCELLING'&&<p>Stopping the worker and its scientific subprocesses…</p>}
      {job.state==='CANCELLED'&&<p>Analysis cancelled. Partial output is retained and is not published as a verified result.</p>}
      {job.error&&<section role="alert" className="error-panel"><h2>{job.error.message}</h2><details><summary>Technical details</summary><p>State: {job.state} · Code: {job.error.code} · Stage: {job.error.stage_id||'Before scientific stages / final verification'}</p><pre>{job.error.detail}</pre></details></section>}
      {job.state==='COMPLETED'&&job.workspace_id&&<button className="primary" disabled={busy} onClick={async()=>{setBusy(true);try{await onOpen(job.workspace_id!)}catch(e){setError(String(e))}finally{setBusy(false)}}}>Open Results</button>}
      <details><summary>Ordered job events</summary><ol>{events.map(e=><li key={e.sequence}>{e.sequence} · {e.timestamp} · {e.state} · {e.stage_id} · {e.status}{e.code&&` · ${e.code}`}</li>)}</ol></details>
      <details><summary>Canonical input metadata hashes</summary><Fields values={job.input_metadata} caption="Execution inputs"/></details>
      {onRecovery&&['FAILED','CANCELLED'].includes(job.state)&&<button disabled={busy} onClick={async()=>{setBusy(true);try{onRecovery(await api<RecoveryView>(`jobs/${jobId}/recovery`,{}))}catch(e){setError(e instanceof ViewerFailure?`${e.detail.code}: ${e.detail.detail}`:String(e))}finally{setBusy(false)}}}>Inspect Recovery</button>}
      <p>Recovery requires a separate read-only preview and explicit confirmation. Job history stays available while this local server is running.</p>
    </>}
    <dialog ref={dialog} aria-labelledby="cancel-title" onCancel={()=>{setConfirm(false);cancelButton.current?.focus()}}><h2 id="cancel-title">Cancel this analysis?</h2><p>The worker and its subprocesses will stop. Any partial output will remain incomplete.</p><button autoFocus onClick={()=>{setConfirm(false);cancelButton.current?.focus()}}>Keep running</button><button onClick={()=>void cancel()}>Confirm cancellation</button></dialog>
  </main>;
}
