import { useCallback, useEffect, useRef, useState } from 'react';
import type { Capabilities, ErrorDetail, Registration, Source, WorkspaceView } from '../models/api';
import { api, download, initializeToken, ViewerFailure } from '../api/client';
import { Status } from '../components/Common';
import { Overview, Samples, QC, Statistics, Provenance } from '../pages/Results';
const tabs=['Overview','Samples','QC','Statistics','Provenance'] as const;
type Tab=typeof tabs[number];
const pages={Overview,Samples,QC,Statistics,Provenance};

export default function App() {
  const [catalog,setCatalog]=useState<Registration[]>([]);const [cap,setCap]=useState<Capabilities|null>(null);const [selected,setSelected]=useState('');
  const [view,setView]=useState<WorkspaceView|null>(null);const [error,setError]=useState<ErrorDetail|null>(null);const [busy,setBusy]=useState(false);
  const [tab,setTab]=useState<Tab>('Overview');const [sample,setSample]=useState('');const [series,setSeries]=useState('');const generation=useRef(0);const openedHeading=useRef<HTMLHeadingElement>(null);const focusOpened=useRef(false);
  const fail=useCallback((e:unknown)=>{setView(null);setError(e instanceof ViewerFailure ? e.detail : {code:'CONNECTION_FAILED',message:'The viewer could not verify the workspace. Results have been hidden.',detail:String(e),stage_id:null});},[]);
  useEffect(()=>{initializeToken();Promise.all([api<Capabilities>('capabilities'),api<Registration[]>('workspaces')]).then(([c,r])=>{setCap(c);setCatalog(r);setSelected(r[0]?.registration_id||'')}).catch(fail)},[fail]);
  useEffect(()=>{if(!view||busy)return;const id=view.workspace_id;let active=true;let timer:ReturnType<typeof setTimeout>;
    const check=async()=>{try{await api<WorkspaceView>(`workspaces/${id}`);if(active)timer=setTimeout(check,15000)}catch(e){if(active)fail(e)}};
    timer=setTimeout(check,15000);return()=>{active=false;clearTimeout(timer)}},[view?.workspace_id,busy,fail]);
  useEffect(()=>{if(!busy&&view&&focusOpened.current){openedHeading.current?.focus();focusOpened.current=false}},[view,busy]);
  async function open() {
    if(busy)return;const g=++generation.current;setView(null);setError(null);setBusy(true);
    try {const v=await api<WorkspaceView>('workspaces/open',{registration_id:selected});if(g!==generation.current)return;
      focusOpened.current=true;setView(v);setSample(v.observations[0]?.sample_id||'');setSeries(v.observations.find(o=>o.metric_name===(v.mode==='precise_edit'?'total_precise_pe':'indel_fraction'))?.series_id||'');setTab('Overview');
    }catch(e){if(g===generation.current)fail(e)}finally{if(g===generation.current)setBusy(false)}
  }
  async function changeTab(next:Tab) {
    if(!view)return;const id=view.workspace_id;const g=++generation.current;setBusy(true);
    try {await api<WorkspaceView>(`workspaces/${id}`);if(g===generation.current)setTab(next)}catch(e){if(g===generation.current)fail(e)}finally{if(g===generation.current)setBusy(false)}
  }
  async function artifact(source:Source) {
    if(!view)return;try{await download(view.workspace_id,source.artifact_id,source.name)}catch(e){fail(e)}
  }
  const Component=pages[tab];
  const sampleChoices=view?[...new Map(view.observations.map(o=>[o.sample_id,o])).values()]:[];
  const seriesChoices=view?[...new Map(view.observations.map(o=>[o.series_id,o])).values()]:[];
  return <><a className="skip-link" href="#main">Skip to results</a><header className="app-header"><div className="brand"><span className="brand-mark" aria-hidden="true">PE</span><strong>PEAnalyzer</strong><span className="muted">Verified result viewer</span></div><span className="read-only">Read-only · {cap?.package_version||'Local'}</span></header>
    <div className="workspace-bar"><label>Registered workspace<select value={selected} disabled={busy} onChange={e=>{setSelected(e.target.value);setView(null);setError(null)}}>{catalog.map(c=><option key={c.registration_id} value={c.registration_id}>{c.label}</option>)}</select></label><button className="primary" disabled={!selected} aria-disabled={busy} onClick={open}>Open and verify</button>{view&&<button disabled={busy} onClick={()=>{generation.current++;setView(null)}}>Close workspace</button>}<span role="status">{busy?'Verifying source integrity…':view?'✓ Verified snapshot':'Select an existing completed analysis'}</span></div>
    {error&&<section className="error-panel" role="alert"><h2>{error.message}</h2><p>No scientific results are displayed.</p><details><summary>Technical details</summary><p>{error.code}{error.stage_id&&` · ${error.stage_id}`}</p><pre>{error.detail}</pre></details></section>}
    {!view&&!error&&<main id="main" className="welcome"><p className="eyebrow">EXISTING ANALYSES</p><h1>Inspect verified results.</h1><p>Open a registered, completed PEAnalyzer workspace to explore biological outcomes, population evidence and provenance.</p><div className="panel"><h2>One scientific source of truth</h2><p>Stored results are verified by Python before display. This viewer performs no analysis and leaves scientific workspaces unchanged.</p><p>Register another workspace with <code>peanalyzer-viewer --workspace PATH</code>.</p></div></main>}
    {view&&<div className="analysis"><section className="analysis-header"><div><p className="eyebrow">COMPLETED ANALYSIS</p><h1 ref={openedHeading} tabIndex={-1}>{view.label}</h1><p>Target {view.targets.join(', ')} · <strong>{view.mode==='precise_edit'?'Precise Edit':'Indel / Nuclease'}</strong></p></div><Status value="Verified"/></section>
      <div className="scope-strip"><label>Biological sample<select value={sample} onChange={e=>setSample(e.target.value)}>{sampleChoices.map(o=><option key={o.sample_id} value={o.sample_id}>{o.sample_name} · {o.sample_id}</option>)}</select></label><label>Stored metric series<select value={series} onChange={e=>setSeries(e.target.value)}>{seriesChoices.map(o=><option key={o.series_id} value={o.series_id}>{o.label}{o.copy_name?` · copy ${o.copy_name}`:''}{o.policy_id?` · ${o.policy_id}`:''} · {o.population_scope}</option>)}</select></label></div>
      <nav aria-label="Result views"><div className="tabs" role="tablist">{tabs.map((t,i)=><button key={t} role="tab" id={`tab-${t}`} aria-controls="result-panel" aria-selected={tab===t} tabIndex={tab===t?0:-1} onClick={()=>changeTab(t)} onKeyDown={e=>{if(['ArrowRight','ArrowLeft','Home','End'].includes(e.key)){e.preventDefault();const n=e.key==='Home'?0:e.key==='End'?4:(i+(e.key==='ArrowRight'?1:4))%5;document.getElementById(`tab-${tabs[n]}`)?.focus();void changeTab(tabs[n])}}}>{t}</button>)}</div></nav>
      <main id="main"><section id="result-panel" role="tabpanel" aria-labelledby={`tab-${tab}`} aria-busy={busy}><Component view={view} sample={sample} series={series} onDownload={artifact} onError={fail}/></section></main>
    </div>}<footer>PEAnalyzer · stored scientific evidence · no analysis execution</footer></>;
}
