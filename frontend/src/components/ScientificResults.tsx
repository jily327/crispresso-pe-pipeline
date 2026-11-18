import type { ScientificPanel, Source } from '../models/api';
import { absent, Fields, SourceLink, Status, Table } from './Common';

export function ScientificResults({panels, onDownload, qc=false}: {
  panels: ScientificPanel[]; onDownload:(source:Source)=>void; qc?:boolean
}) {
  const selected = panels.filter(p => qc ? p.evidence.length > 0 || p.reasons.length > 0 || !p.measurements.length : p.measurements.length > 0 || p.status === 'BLOCKED');
  if (!selected.length) return null;
  return <section><h3>{qc ? 'Sample assessment and exclusions' : 'Measurements by population'}</h3>
    {selected.map(p => <article className="panel" key={JSON.stringify([p.target,p.method,p.population])}>
      <h4>{p.method} · {p.population}</h4><p>{p.target} · {p.sample_id} · <Status value={p.status}/></p>
      {p.definition && <p>{p.definition}</p>}
      {p.reasons.length > 0 && <p>{p.reasons.join(' · ')}</p>}
      {qc && p.evidence.length > 0 && <Fields values={p.evidence} caption={p.method+' evidence'}/>}
      {!qc && p.measurements.length > 0 && <Table caption={p.method+' · '+p.population} headers={['Outcome','Numerator','Denominator','Fraction (%)']}>
        {p.measurements.map(m => <tr key={m.name}><th scope="row">{m.name}</th><td>{absent(m.numerator)}</td><td>{absent(m.denominator)}</td><td>{m.percentage ?? 'Not assessable'}</td></tr>)}</Table>}
      {!qc && p.evidence.length > 0 && <details><summary>Counts and assessment evidence</summary><Fields values={p.evidence} caption={p.method+' evidence'}/></details>}
      <SourceLink source={p.source} onDownload={onDownload}/>
    </article>)}</section>;
}
