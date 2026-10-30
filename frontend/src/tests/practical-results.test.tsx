import {render,screen,within} from '@testing-library/react';
import {expect,it,vi} from 'vitest';
import {Samples} from '../pages/Results';
import type {WorkspaceView} from '../models/api';
import peRaw from './fixtures/pe.json';
const view={...peRaw,observations:peRaw.observations.map(o=>({...o,label:o.metric_name==='target_crispresso_native_pe'?'CRISPResso Prime-edited reference fraction':o.label,numerator_label:'Authoritative numerator',definition:'Authoritative stored definition'}))} as WorkspaceView;
it('shows both primary fractions and exact stored integers simultaneously',()=>{
  const v=structuredClone(view);const primary=v.observations.find(o=>o.metric_name==='total_precise_pe')!;const native=v.observations.find(o=>o.sample_id===primary.sample_id&&o.metric_name==='target_crispresso_native_pe')!;
  primary.percentage='12.345%';primary.numerator='999';primary.denominator='1';native.percentage='67.891%';
  render(<Samples view={v} sample={primary.sample_id} series={primary.series_id} onDownload={vi.fn()} onError={vi.fn()}/>);
  const table=within(screen.getByRole('table',{name:'Primary PE metrics across biological samples'}));
  expect(table.getByRole('columnheader',{name:'Exact intended PE'})).toBeVisible();expect(table.getByRole('columnheader',{name:'CRISPResso Prime-edited reference fraction'})).toBeVisible();
  expect(table.getByText('12.345%')).toBeVisible();expect(table.getByText('67.891%')).toBeVisible();expect(table.getByText('999 / 1')).toBeVisible();
});
it('retains blocked/null and routing diagnostics without a zero substitute',()=>{
  const v=structuredClone(view);const primary=v.observations.find(o=>o.metric_name==='total_precise_pe')!;
  primary.status='BLOCKED';primary.percentage=null;primary.fraction=null;primary.numerator=null;primary.denominator=null;primary.reasons=['SCIENCE_GATE'];
  const routed=v.observations.find(o=>o.routing_conditioned)!;
  render(<Samples view={v} sample={primary.sample_id} series={routed.series_id} onDownload={vi.fn()} onError={vi.fn()}/>);
  const row=within(screen.getByRole('table',{name:'Primary PE metrics across biological samples'})).getByText('SCIENCE_GATE').closest('tr')!;
  expect(within(row).getByText('— / —')).toBeVisible();expect(within(row).queryByText('0%')).not.toBeInTheDocument();
  expect(screen.getByText(/Copy-specific routed diagnostics:/)).toBeVisible();
});
