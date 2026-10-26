import { render, screen, within, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { WorkspaceView, Observation } from '../models/api';
import peRaw from './fixtures/pe.json';
import nucleaseRaw from './fixtures/nuclease.json';
import { MetricCard } from '../components/Common';
import { Overview, Statistics, Samples, Provenance } from '../pages/Results';
const pe=peRaw as WorkspaceView;const nuclease=nucleaseRaw as WorkspaceView;
const primary=(v:WorkspaceView)=>v.observations.find(o=>o.metric_name===(v.mode==='precise_edit'?'total_precise_pe':'indel_fraction'))!;
const props=(v:WorkspaceView)=>({view:v,sample:primary(v).sample_id,series:primary(v).series_id,onDownload:vi.fn(),onError:vi.fn()});

describe('frontend scientific ownership',()=>{
  it('renders the backend percentage even when fixture counts deliberately disagree',()=>{
    const row={...primary(pe),numerator:'999999999999999999999999',denominator:'1',fraction:0.12345,percentage:'12.345%'};
    render(<MetricCard row={row} onDownload={vi.fn()}/>);
    expect(screen.getByText('12.345%')).toBeVisible();expect(screen.getByText('999999999999999999999999 / 1')).toBeVisible();
  });
  it('keeps unavailable distinct from reportable zero',()=>{
    const row={...primary(pe),numerator:null,denominator:null,fraction:null,percentage:null,status:'NOT_ASSESSABLE',reasons:['NO_DENOMINATOR']} as Observation;
    const {rerender}=render(<MetricCard row={row} onDownload={vi.fn()}/>);
    expect(screen.queryByText('0%')).not.toBeInTheDocument();expect(screen.getByText('— / —')).toBeVisible();
    rerender(<MetricCard row={{...row,status:'REPORTABLE',numerator:'0',denominator:'20',fraction:0,percentage:'0%',reasons:[]}} onDownload={vi.fn()}/>);
    expect(screen.getByText('0%')).toBeVisible();
  });
  it('uses stored condition mean rather than pooling sample counts',()=>{
    const v=structuredClone(pe);v.groups=v.groups.filter(g=>g.series_id===primary(v).series_id);
    v.groups[0].mean=0.4321;v.groups[0].mean_percentage='43.21%';v.observations.forEach(o=>{o.numerator='0';o.denominator='999999'});
    render(<Statistics {...props(v)}/>);expect(screen.getByText('43.21%')).toBeVisible();
  });
  it('displays stored effect, p, q and biological n unchanged',()=>{
    const v=structuredClone(pe);const c=v.contrasts[0];render(<Statistics {...props(v)} series={c.series_id}/>);
    expect(screen.getAllByText(String(c.p)).length).toBeGreaterThan(0);
    expect(screen.getByText(`${c.used_a} / ${c.expected_a}; ${c.used_b} / ${c.expected_b}`)).toBeVisible();
  });
  it('preserves explicit descriptive-only state',()=>{
    const v={...pe,contrasts:[]};render(<Statistics {...props(v)}/>);
    expect(screen.getByText('Descriptive summaries only — no statistical tests requested.')).toBeVisible();
  });
  it('keeps exclusive and overlapping metrics separate without normalization',()=>{
    const v=structuredClone(nuclease);v.nuclease[0].overlapping[0].percentage='91.234%';v.nuclease[0].overlapping[1].percentage='91.234%';
    render(<Overview {...props(v)}/>);
    expect(screen.getByRole('table',{name:'Exclusive biological classes · accepted aligned population'})).toBeVisible();
    expect(within(screen.getByRole('table',{name:'Overlapping metrics — do not sum'})).getAllByText('91.234%')).toHaveLength(2);
  });
  it('preserves a net-zero indel bin as an indel',()=>{
    const v=structuredClone(nuclease);v.nuclease[0].bins=[{net_size:'0',numerator:'12',denominator:'12',fraction:1,percentage:'100%'}];
    render(<Overview {...props(v)}/>);expect(screen.getByText('0 · Net zero indel')).toBeVisible();
  });
  it.each(['W1','W2','W3','W4','explicit'])('renders stored %s window without geometry calculations',(selected)=>{
    const v=structuredClone(nuclease);v.nuclease[0].window=[{name:'selected_window',value:selected},{name:'coordinates',value:'17-19_30-31'},{name:'orientation',value:'palindromic'},{name:'target_oriented_nick_labels',value:null}];
    render(<Overview {...props(v)}/>);expect(screen.getByText(selected)).toBeVisible();expect(screen.getByText('17-19_30-31')).toBeVisible();expect(screen.getByText('palindromic')).toBeVisible();
  });
  it('shows PE exact/native separately with their own denominators',()=>{
    render(<Overview {...props(pe)}/>);expect(screen.getByRole('heading',{name:'Exact intended PE'})).toBeVisible();expect(screen.getByRole('heading',{name:'CRISPResso native PE'})).toBeVisible();
    expect(screen.getByText('Exact WT + exact PE products')).toBeVisible();expect(screen.getByText('Authoritative aligned reads')).toBeVisible();
  });
  it('filters sample rows without recomputing scientific values',()=>{
    render(<Samples {...props(pe)}/>);fireEvent.change(screen.getByLabelText('Filter samples'),{target:{value:'bc001'}});
    expect(screen.getByText('bc001')).toBeVisible();expect(screen.queryByText('bc002')).not.toBeInTheDocument();
  });
  it('never embeds native HTML and reports absence explicitly',()=>{
    const v={...pe,native_html:'Not produced'} as WorkspaceView;
    const {container}=render(<Provenance {...props(v)}/>);expect(screen.getByText('Not produced')).toBeVisible();expect(container.querySelectorAll('iframe,object,embed')).toHaveLength(0);
  });
});
