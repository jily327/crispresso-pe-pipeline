import type { ReactNode } from 'react';
import type { FieldValue, Observation, Source } from '../models/api';
export const absent = (value: string | number | null | undefined) => value ?? '—';
export function Status({ value }: { value: string }) {
  return <span className={`status ${value === 'REPORTABLE' || value === 'Verified' ? 'ok' : 'unavailable'}`}>{value === 'REPORTABLE' || value === 'Verified' ? '✓' : 'ⓘ'} {value.replaceAll('_', ' ')}</span>;
}
export function Table({ caption, headers, children }: { caption: string; headers: string[]; children: ReactNode }) {
  return <div className="table-scroll" tabIndex={0} role="region" aria-label={caption}><table><caption>{caption}</caption><thead><tr>{headers.map(h => <th key={h} scope="col">{h}</th>)}</tr></thead><tbody>{children}</tbody></table></div>;
}
export function Fields({ values, caption = 'Stored evidence' }: { values: FieldValue[]; caption?: string }) {
  return <Table caption={caption} headers={['Field', 'Stored value']}>{values.map(v => <tr key={v.name}><th scope="row">{v.name}</th><td className="literal">{absent(v.value)}</td></tr>)}</Table>;
}
export function SourceLink({ source, onDownload }: { source: Source; onDownload: (s: Source) => void }) {
  return <button className="link" disabled={!source.downloadable} onClick={() => onDownload(source)}>Source · {source.name}</button>;
}
export function MetricCard({ row, onDownload }: { row: Observation; onDownload: (s: Source) => void }) {
  return <article className="metric-card"><div className="card-top"><h3>{row.label}</h3><Status value={row.status}/></div>
    <p className="metric-value">{absent(row.percentage)}</p><p className="ratio">{absent(row.numerator)} / {absent(row.denominator)}</p>
    <p>{row.definition}</p><p>Numerator: {row.numerator_label||'See stored metric evidence'}</p><p>Denominator: {row.denominator_label}</p><p className="muted">{row.assessment_stage} · {row.backend_counts_role}</p>
    <p className="muted">{row.population_scope}{row.routing_conditioned ? ' · Routing-conditioned copy' : ''}</p>
    {row.reasons.length > 0 && <p>{row.reasons.join(' · ')}</p>}
    <details><summary>Exact value and population</summary><p>Stored fraction: {absent(row.fraction)}</p><p className="literal">{row.population_id}</p><Fields values={row.policy} caption="Stored policy"/></details>
    <SourceLink source={row.source} onDownload={onDownload}/></article>;
}
