import {useEffect,useRef,useState} from 'react';
import {api,ViewerFailure} from '../api/client';
import {Fields,Table} from '../components/Common';
import type {Registration,WorkspaceView} from '../models/api';
import type {JobView} from '../models/jobs';
import type {RecoveryView} from '../models/recovery';

export function Recovery({initial,onAccepted,onOpen}:{initial:RecoveryView|null;onAccepted:(j:JobView)=>void;onOpen:(id:string)=>Promise<void>}) {
  const [catalog,setCatalog]=useState<Registration[]>([]),[selected,setSelected]=useState('');
  const [view,setView]=useState<RecoveryView|null>(initial),[force,setForce]=useState<string[]>([]);
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[confirmed,setConfirmed]=useState(false),[changed,setChanged]=useState(false);
  const generation=useRef(0),heading=useRef<HTMLHeadingElement>(null);
  useEffect(()=>{heading.current?.focus();let live=true;api<Registration[]>('recovery/workspaces').then(rows=>{if(live){setCatalog(rows);setSelected(rows[0]?.registration_id||'')}}).catch(e=>{if(live)setError(String(e))});return()=>{live=false;generation.current++}},[]);
  useEffect(()=>{setView(initial);setForce(initial?.selected_force||[]);setConfirmed(false);setChanged(false)},[initial]);
  function fail(e:unknown){setError(e instanceof ViewerFailure?`${e.detail.code}: ${e.detail.detail}`:String(e));setConfirmed(false)}
  async function inspect(refresh=false){const g=++generation.current;setBusy(true);setError('');setConfirmed(false);
    try {const next=refresh&&view?await api<RecoveryView>(`recovery/${view.recovery_id}/preview`,{revision:view.revision,force}):await api<RecoveryView>('recovery',{registration_id:selected});
      if(g!==generation.current)return;setView(next);setForce(next.selected_force);setChanged(false);
    }catch(e){if(g===generation.current){fail(e);setChanged(true)}}finally{if(g===generation.current)setBusy(false)}}
  async function execute(){if(!view||!confirmed||changed)return;setBusy(true);setError('');try{onAccepted(await api<JobView>(`recovery/${view.recovery_id}/execute`,{revision:view.revision,recovery_plan_sha256:view.recovery_plan_sha256,confirmed:true}))}catch(e){fail(e);setChanged(true)}finally{setBusy(false)}}
  async function open(){if(!view)return;setBusy(true);try{const opened=await api<WorkspaceView>(`recovery/${view.recovery_id}/open`,{});await onOpen(opened.workspace_id)}catch(e){fail(e)}finally{setBusy(false)}}
  return <main className="setup" id="recovery-main"><p className="eyebrow">RECOVER ANALYSIS</p><h1 tabIndex={-1} ref={heading}>Inspect before recovery.</h1>
    <p>Inspection is read-only. Python validates source identity, reusable stages and the exact force closure. Nothing is deleted or executed until you confirm a current preview.</p>
    <label>Registered recovery workspace<select value={selected} disabled={busy} onChange={e=>{generation.current++;setSelected(e.target.value);setView(null);setConfirmed(false);setForce([]);setChanged(false)}}>{catalog.map(r=><option key={r.registration_id} value={r.registration_id}>{r.label}</option>)}</select></label>
    <button disabled={busy||!selected} onClick={()=>void inspect()}>Inspect workspace</button>
    {!catalog.length&&<p>Register an incomplete workspace with <code>peanalyzer-viewer --recover-workspace PATH</code>, or choose Inspect Recovery after a failed or cancelled analysis.</p>}
    {error&&<p role="alert" className="error-panel">{error}</p>}
    {view&&<><h2>{view.workspace_label}</h2><p role="status">{busy?'Inspecting / confirming…':view.classification}</p><p>Analysis mode: {view.analysis_mode||'Unavailable'}</p>
      <dl className="identities"><dt>Scientific identity</dt><dd>{view.scientific_identity_sha256||'Unavailable'}</dd><dt>Stored workflow identity</dt><dd>{view.workflow_identity_sha256||'Unavailable'}</dd><dt>Recovery plan identity</dt><dd>{view.recovery_plan_sha256||'No executable preview'}</dd></dl>
      {view.reasons.length>0&&<section aria-label="Recovery reasons"><h3>Backend reasons</h3><ul>{view.reasons.map((r,i)=><li key={i}>{r.code} · {r.stage_id} · {r.detail}</li>)}</ul></section>}
      {view.classification==='COMPLETED'?<><p>This workspace already verifies. Recovery is unnecessary.</p><button className="primary" disabled={busy} onClick={()=>void open()}>Open Results</button></>:<>
        <details><summary>Advanced: force selected stage families</summary><p>Force removes owned stage outputs and their downstream results. It is not a generic retry. Select families, request a fresh preview, and review every affected path before confirmation.</p>
          <fieldset disabled={busy}><legend>Backend-provided force families</legend>{view.force_families.map(f=><label key={f}><input type="checkbox" checked={force.includes(f)} onChange={e=>{setForce(previous=>e.target.checked?[...previous,f]:previous.filter(x=>x!==f));setChanged(true);setConfirmed(false)}}/>{f}</label>)}</fieldset>
        </details>
        <button disabled={busy} onClick={()=>void inspect(true)}>Preview recovery selection</button>
        {changed&&<p role="status">The selection or workspace changed. Request a new preview before confirmation.</p>}
        <p>Requested families: {view.selected_force.join(', ')||'None — normal resume'}</p>
        <Table caption="Backend recovery stage plan" headers={['Stage','Kind','Action','Output path','Reason']}>{view.stages.map(s=><tr key={s.stage_id}><th scope="row">{s.stage_id}</th><td>{s.stage_kind}</td><td>{s.action}</td><td>{s.output_path}</td><td>{s.reason_codes.join(', ')||'Backend completion / dependency validation'}</td></tr>)}</Table>
        <h3>Affected stage closure</h3>{view.closure.length?<ul>{view.closure.map(s=><li key={s}>{s}</li>)}</ul>:<p>No forced stages.</p>}
        <h3>Owned paths to remove or replace</h3>{view.removal_paths.length?<ul className="literal">{view.removal_paths.map(p=><li key={p}>{p}</li>)}</ul>:<p>No forced deletion.</p>}
        {view.executable&&<><label><input type="checkbox" disabled={busy||changed} checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>I reviewed this recovery plan and confirm {view.selected_force.length?'the listed removals and reruns':'reuse of verified stages and execution of incomplete stages'}.</label><button className="primary" disabled={busy||changed||!confirmed} onClick={()=>void execute()}>{view.selected_force.length?'Confirm forced recovery':'Confirm resume'}</button></>}
      </>}
      <details><summary>Software and backend identity</summary><Fields values={view.software} caption="Recovery software"/><Fields values={view.backend} caption="Recovery backend"/></details>
      <p>Original inputs and persistent GUI metadata must remain available. Existing invocation locks are never stolen. An active supervisor blocks new science, including after server restart.</p>
    </>}
  </main>;
}
