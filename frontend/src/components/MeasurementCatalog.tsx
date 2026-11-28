import type { MeasurementRow, NativeRunView, Source } from '../models/api';
import { Fields, Status, Table, absent } from './Common';

const groups = ['Original CRISPResso2 2.3.4 results', 'PEAnalyzer-derived CRISPResso allele measurements',
  'Independent PEAnalyzer sequence measurements', 'Reconciliation and scientific QC'];

export function MeasurementCatalog({rows,runs,onDownload}: {
  rows:MeasurementRow[]; runs:NativeRunView[]; onDownload:(source:Source)=>void;
}) {
  if (!rows.length) return null;
  return <section aria-label="Scientific measurement sources">{groups.map((group,i)=>{
    const items = rows.filter(row=>row.measurement_source===group);
    return <section key={group}><h3>{group}</h3>
      {i===0 && runs.map(run=><article className="panel" key={run.run_id}><h4>{run.mode} · {run.run_id}</h4>
        <p>{run.population} · Execution {run.execution} · Native extraction {run.extraction} · Allele recount {run.recount} · Direct reproduction {run.direct_parity} · Runtime {run.evidence.find(f=>f.name==='runtime_identity_status')?.value ?? 'UNVERIFIED'}</p>
        <details><summary>Inputs, references, effective windows and command</summary><Fields values={run.evidence}/></details>
        <div className="pager">{run.files.map(f=><button type="button" key={f.role} disabled={!f.source.downloadable} onClick={()=>onDownload(f.source)}>{f.role} · {f.source.name.split('/').at(-1)}</button>)}</div>
      </article>)}
      {items.length ? <details><summary>{items.length} stored measurements and observations</summary>
        <Table caption={group} headers={['Measurement','Population / reference','Count / observation','Numerator / denominator','Fraction','Eligibility and evidence']}>{items.map((m,index)=>
          <tr key={index}><th scope="row">{m.measurement}<small>{m.definition}</small></th><td>{m.population}<small>{[m.copy_name,m.reference,m.native_execution_id].filter(Boolean).join(' · ')}</small></td>
          <td>{absent(m.integer_count ?? m.observation)}</td><td>{m.numerator===null&&m.denominator===null?'—':absent(m.numerator)+' / '+absent(m.denominator)}</td><td>{m.fraction===null?'—':m.fraction}</td><td><Status value={m.eligibility}/><small>{m.reasons.join(' · ')}</small><small>{m.source_artifact} · {m.source_sha256}</small></td></tr>)}</Table>
        </details>:<p>No measurement in this group for the selected sample.</p>}
    </section>;
  })}</section>;
}
