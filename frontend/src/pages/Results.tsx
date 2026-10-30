import { useEffect, useRef, useState } from 'react';
import type { WorkspaceView, Observation, Source, NucleaseDetail, AllelePage, Group } from '../models/api';
import { api } from '../api/client';
import { absent, Fields, MetricCard, SourceLink, Status, Table } from '../components/Common';

type Props = { view: WorkspaceView; sample: string; series: string; onDownload: (s: Source) => void; onError: (e: unknown) => void };
export function Groups({ groups }: { groups: Group[] }) {
  return <Table caption="Biological replicate summaries · stored unweighted means" headers={['Condition', 'Metric', 'Mean', 'Reportable / expected n', 'Minimum fraction', 'Maximum fraction', 'Median fraction', 'Sample points and availability']}>{groups.map((g,i) => <tr key={i}><th scope="row">{g.condition}</th><td>{g.label}</td><td>{absent(g.mean_percentage)}</td><td>{g.reportable_n} / {g.expected_n}</td><td>{absent(g.minimum)}</td><td>{absent(g.maximum)}</td><td>{absent(g.median)}</td><td><details><summary>Biological samples</summary><Fields values={g.points} caption="Stored sample fractions"/><Fields values={g.availability} caption="Sample availability"/></details></td></tr>)}</Table>;
}
function Nuclease({ detail }: { detail: NucleaseDetail }) {
  return <><Fields values={detail.window} caption="Selected window · 0-based inclusive, amplicon top strand"/>
    <Table caption="Exclusive biological classes · accepted aligned population" headers={['Class', 'Reads', 'Aligned denominator', 'Stored percentage']}>{detail.classes.map(c => <tr key={c.name}><th scope="row">{c.name}</th><td>{absent(c.numerator)}</td><td>{absent(c.denominator)}</td><td>{absent(c.percentage)}</td></tr>)}</Table>
    <Table caption="Overlapping metrics — do not sum" headers={['Metric', 'Reads', 'Aligned denominator', 'Stored percentage']}>{detail.overlapping.map(c => <tr key={c.name}><th scope="row">{c.name}</th><td>{absent(c.numerator)}</td><td>{absent(c.denominator)}</td><td>{absent(c.percentage)}</td></tr>)}</Table>
    <Table caption="Net indel size within quantification window" headers={['Net size (bp)', 'Bin reads', 'Indel-containing denominator', 'Stored percentage']}>{detail.bins.map(b => <tr key={b.net_size}><th scope="row">{b.net_size === '0' ? '0 · Net zero indel' : b.net_size}</th><td>{absent(b.numerator)}</td><td>{absent(b.denominator)}</td><td>{absent(b.percentage)}</td></tr>)}</Table>
    {!detail.bins.length && <p>No indel-containing reads for this distribution.</p>}</>;
}
export function Overview(p: Props) {
  const primary = p.view.mode === 'precise_edit' ? 'total_precise_pe' : 'indel_fraction';
  const rows = p.view.observations.filter(o => o.sample_id === p.sample && (o.metric_name === primary || o.metric_name === 'target_crispresso_native_pe'));
  const detail = p.view.nuclease.find(n => n.sample_id === p.sample);
  return <><div className="section-heading"><h2>Overview</h2><p>Stored biological outcomes · equal-weight biological replicates</p></div>
    <Groups groups={p.view.groups.filter(g => g.metric_name === primary)}/>
    <h3>Selected biological sample · {rows[0]?.sample_name}</h3><div className="metric-grid">{rows.map(o => <MetricCard key={o.observation_id} row={o} onDownload={p.onDownload}/>)}</div>
    {p.view.mode === 'precise_edit' && <p className="callout">Exact intended PE and the CRISPResso Prime-edited reference fraction describe different populations and denominators. Neither metric is a lower bound for the other.</p>}
    {detail && <Nuclease detail={detail}/>}</>;
}
function Alleles(p: Props) {
  const [page,setPage]=useState<AllelePage | null>(null);const [offset,setOffset]=useState(0);
  useEffect(() => { setPage(null);let active=true;api<AllelePage>(`workspaces/${p.view.workspace_id}/alleles/${p.sample}?offset=${offset}&limit=20`).then(v=>{if(active)setPage(v)}).catch(e=>{if(active)p.onError(e)});return()=>{active=false}; },[p.view.workspace_id,p.sample,offset]);
  return <section><h4>Authoritative nuclease allele rows · window-aware events</h4>{!page ? <p role="status">Verifying allele source…</p> : <><Table caption={`Alleles · ${page.total} stored rows`} headers={['Reads','Class','Inserted bp','Deleted bp','Mutated bp','Net delta','Authoritative sequences']}>{page.items.map(a=><tr key={a.row_id}><td>{a.reads}</td><td>{a.product_class}</td><td>{a.inserted_bp}</td><td>{a.deleted_bp}</td><td>{a.mutated_bp}</td><td>{a.net_delta}</td><td><details><summary>Literal aligned / reference strings</summary><pre>{a.aligned_sequence}{'\n'}{a.reference_sequence}</pre><p>Original CRISPResso %Reads: {a.original_percentage}</p></details></td></tr>)}</Table><div className="pager"><button disabled={offset===0} onClick={()=>setOffset(offset-20)}>Previous allele page</button><span>Offset {offset} · {page.total} rows</span><button disabled={BigInt(offset+20)>=BigInt(page.total)} onClick={()=>setOffset(offset+20)}>Next allele page</button></div></>}</section>;
}
function PrimaryPESamples(p:Props & {query:string;status:string}) {
  // Join stored observations by biological sample and target. Never derive a fraction.
  const primary=p.view.observations.filter(o=>!o.routing_conditioned&&o.copy_name===null&&['total_precise_pe','target_crispresso_native_pe'].includes(o.metric_name));
  const keys=[...new Set(primary.map(o=>JSON.stringify([o.sample_id,o.target])))].sort();
  function cell(values:Observation[]) {
    if(!values.length)return <span>Not available</span>;
    // Keep distinct policy/population observations explicit rather than selecting one silently.
    return values.map(o=><div key={o.observation_id}><strong>{absent(o.percentage)}</strong><p>{absent(o.numerator)} / {absent(o.denominator)}</p><Status value={o.status}/><p>{o.reasons.join(' · ')}</p>
      <details><summary>Definition and population</summary><p>{o.definition}</p><p>Numerator: {o.numerator_label}</p><p>Denominator: {o.denominator_label}</p><p>Population: {o.population_scope} · {o.population_id}</p><SourceLink source={o.source} onDownload={p.onDownload}/></details></div>);
  }
  return <section aria-label="Primary biological metrics"><h3>Primary biological metrics</h3><p>Both stored PE fractions are shown together. Their numerators and denominators differ; neither is a lower bound for the other.</p>
    <Table caption="Primary PE metrics across biological samples" headers={['Sample / target','Editor / treatment','Dpi / biological replicate','Exact intended PE','CRISPResso Prime-edited reference fraction']}>{keys.map(key=>{
      const [sample,target]=JSON.parse(key);const rows=primary.filter(o=>o.sample_id===sample&&o.target===target);const o=rows[0];
      if(!`${o.sample_name} ${o.sample_id} ${o.editor} ${o.treatment}`.toLowerCase().includes(p.query.toLowerCase())||(p.status!=='all'&&!rows.some(r=>r.status===p.status)))return null;
      return <tr key={key}><th scope="row">{o.sample_name}<small>{o.sample_id} · {target}</small></th><td>{o.editor} / {o.treatment}</td><td>{o.dpi} / {o.biological_replicate}</td><td>{cell(rows.filter(r=>r.metric_name==='total_precise_pe'))}</td><td>{cell(rows.filter(r=>r.metric_name==='target_crispresso_native_pe'))}</td></tr>
    })}</Table>
  </section>;
}
export function Samples(p: Props) {
  const [query,setQuery]=useState('');const [status,setStatus]=useState('all');const [sort,setSort]=useState('sample');const [page,setPage]=useState(0);const [detail,setDetail]=useState<Observation|null>(null);const opener=useRef<HTMLButtonElement|null>(null);const close=useRef<HTMLButtonElement|null>(null);
  useEffect(()=>{setPage(0)},[query,status,sort,p.series]);
  useEffect(()=>{if(detail)close.current?.focus()},[detail]);
  const rows=p.view.observations.filter(o=>o.series_id===p.series && (status==='all'||o.status===status) && `${o.sample_name} ${o.sample_id} ${o.editor} ${o.treatment} ${o.reasons.join(' ')}`.toLowerCase().includes(query.toLowerCase())).sort((a,b)=>sort==='fraction' ? (a.fraction===null?1:b.fraction===null?-1:b.fraction-a.fraction)||a.sample_id.localeCompare(b.sample_id):a.sample_id.localeCompare(b.sample_id));
  const hide=()=>{setDetail(null);opener.current?.focus()};
  return <><h2>Samples</h2><div className="filters"><label>Filter samples<input value={query} onChange={e=>setQuery(e.target.value)}/></label><label>Status<select value={status} onChange={e=>setStatus(e.target.value)}><option value="all">All states</option>{['REPORTABLE','BLOCKED','NOT_ASSESSABLE'].map(s=><option key={s}>{s}</option>)}</select></label><label>Sort<select value={sort} onChange={e=>setSort(e.target.value)}><option value="sample">Stable sample ID</option><option value="fraction">Stored fraction · unavailable last</option></select></label></div>
    {p.view.mode==='precise_edit'&&<PrimaryPESamples {...p} query={query} status={status}/>}
    <h3>{p.view.mode==='precise_edit'?'Selected-series detail · advanced exploration':'Biological sample observations'}</h3>
    {rows[0]?.routing_conditioned&&<p className="callout">Copy-specific routed diagnostics: these values are conditional on confident copy routing, not equivalent top-level editing-efficiency estimates.</p>}
    <Table caption="Biological sample observations" headers={['Sample','Editor / treatment','Dpi / biological replicate','Stored percentage','Numerator / denominator','Status','Detail']}>{rows.slice(page*20,page*20+20).map(o=><tr key={o.observation_id}><th scope="row">{o.sample_name}<small>{o.sample_id}</small></th><td>{o.editor} / {o.treatment}</td><td>{o.dpi} / {o.biological_replicate}</td><td>{absent(o.percentage)}</td><td>{absent(o.numerator)} / {absent(o.denominator)}</td><td><Status value={o.status}/>{o.reasons.join(' · ')}</td><td><button onClick={e=>{opener.current=e.currentTarget;setDetail(o)}}>Inspect {o.sample_name}</button></td></tr>)}</Table>
    <div className="pager"><button disabled={!page} onClick={()=>setPage(page-1)}>Previous samples</button><span>{rows.length} observations · page {page+1}</span><button disabled={(page+1)*20>=rows.length} onClick={()=>setPage(page+1)}>Next samples</button></div>
    {detail && <section className="detail-panel" role="region" aria-label="Sample detail" onKeyDown={e=>{if(e.key==='Escape')hide()}}><button ref={close} onClick={hide}>Close sample detail</button><h3>{detail.sample_name} · {detail.sample_id}</h3><MetricCard row={detail} onDownload={p.onDownload}/><Fields values={detail.evidence} caption="Stored metric count evidence"/>{p.view.mode==='indel_nuclease'&&<Alleles {...p} sample={detail.sample_id} key={detail.sample_id}/>}</section>}</>;
}
export function QC(p: Props) {
  return <><h2>QC · named populations</h2><p className="callout">{p.view.mode==='precise_edit'?'Prepared exact assessment, native CRISPResso and copy routing retain their backend-defined relationships. This is not a universal input → aligned → exact funnel.':'Single-copy identity; no PE routing. Accepted aligned outcomes have four ordinary biological classes.'}</p>{p.view.populations.filter(v=>v.sample_id===null||v.sample_id===p.sample).map((q,i)=><section className="panel" key={i}><h3>{q.name}</h3><p>{q.role}</p><Fields values={q.counts} caption="Exact stored population counts"/><SourceLink source={q.source} onDownload={p.onDownload}/></section>)}</>;
}
export function Statistics(p: Props) {
  const groups=p.view.groups.filter(g=>g.series_id===p.series);const contrasts=p.view.contrasts.filter(c=>c.series_id===p.series);
  return <><h2>Statistics</h2><p className="callout">Inference uses biological samples, not sequencing reads. Means and tests below are stored M5 results.</p><Groups groups={groups}/>
    {!p.view.contrasts.length ? <p>Descriptive summaries only — no statistical tests requested.</p> : <><Table caption="Explicit contrasts · effect B − A" headers={['Contrast / family','A → B','Effect','p','q','Used / expected biological n (A; B)','Status','Design']}>{contrasts.map(c=><tr key={c.contrast_id}><th scope="row">{c.contrast_id}<small>{c.family}</small></th><td>{c.group_a} → {c.group_b}</td><td>{absent(c.effect)}</td><td>{absent(c.p)}</td><td>{absent(c.q)}</td><td>{c.used_a} / {c.expected_a}; {c.used_b} / {c.expected_b}</td><td><Status value={c.status}/>{c.reasons.join(' · ')}</td><td><details><summary>{c.pairing_mode}</summary><p>Complete blocks: {c.blocks.join(', ')||'—'}</p><Fields values={c.exclusions} caption="Excluded blocks"/></details></td></tr>)}</Table>{!contrasts.length&&<p>No contrast was requested for this selected series.</p>}</>}</>;
}
export function Provenance(p: Props) {
  const detail=p.view.nuclease.find(n=>n.sample_id===p.sample);const [query,setQuery]=useState('');const [page,setPage]=useState(0);
  const artifacts=p.view.artifacts.filter(s=>s.name.toLowerCase().includes(query.toLowerCase()));
  return <><h2>Provenance</h2><p>Verified snapshot: <code>{p.view.snapshot_id}</code></p><p>Contracts: {p.view.contracts.join(' · ')}</p><Fields values={p.view.provenance} caption="Software, runtime and source identity"/>
    {detail&&<><details><summary>Qualified scientific configuration · backend-validated expected values</summary><Fields values={detail.expected_configuration} caption="Qualified scientific fields"/></details><details><summary>Actual resolved CRISPResso arguments</summary><Fields values={detail.resolved_configuration} caption="Recorded resolved arguments"/></details><Fields values={detail.window} caption="Stored selected window"/></>}
    <Table caption="Recorded stage execution / reuse" headers={['Stage','Status','Recorded action','Signature','Started / ended']}>{p.view.stages.map(s=><tr key={s.stage_id}><th scope="row">{s.label}<small>{s.stage_id}</small></th><td>{s.status}</td><td>{s.history}</td><td className="hash">{s.signature}</td><td>{s.started_at}<br/>{s.ended_at}</td></tr>)}</Table>
    <h3>Verified artifacts</h3><p>Native HTML: <strong>{p.view.native_html}</strong>. HTML and SVG files are downloads only.</p><label>Filter artifact names<input value={query} onChange={e=>{setQuery(e.target.value);setPage(0)}}/></label>
    <Table caption="Manifest-bound artifact inventory" headers={['Artifact','Bytes','SHA-256','Access']}>{artifacts.slice(page*20,page*20+20).map(s=><tr key={s.artifact_id}><th scope="row" className="literal">{s.name}</th><td>{s.size_bytes}</td><td className="hash">{s.sha256}</td><td>{s.downloadable?<button onClick={()=>p.onDownload(s)}>Download</button>:'Inventoried; download unavailable'}</td></tr>)}</Table><div className="pager"><button disabled={!page} onClick={()=>setPage(page-1)}>Previous artifacts</button><span>{artifacts.length} artifacts · page {page+1}</span><button disabled={(page+1)*20>=artifacts.length} onClick={()=>setPage(page+1)}>Next artifacts</button></div></>;
}
