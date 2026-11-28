import {render,screen,within} from '@testing-library/react';
import {expect,it,vi} from 'vitest';
import {ScientificResults} from '../components/ScientificResults';
import type {ScientificPanel} from '../models/api';

it('shows stored site denominators, unavailable percentages and blocked reasons',()=>{
  const base:ScientificPanel = {
    sample_id:'1A',target:'T',method:'Joint calls',population:'Combined target',status:'ASSESSED',
    definition:'Joint denominator counts assessable pairs.',reasons:[],evidence:[],
    source:{name:'intended_sites.json',kind:'json',sha256:'hash',artifact_id:'a',size_bytes:'4',downloadable:true},
    measurements:[{name:'Site A only',numerator:'1',denominator:'7',fraction:1/7,percentage:'14.2857%'}]
  };
  render(<ScientificResults panels={[base,{...base,population:'Unresolved copy',
    measurements:[{name:'Site A only',numerator:'0',denominator:'0',fraction:null,percentage:null}]},
    {...base,method:'Native allele calls',status:'BLOCKED',reasons:['NO_BACKEND_EVIDENCE'],measurements:[]}]}
    onDownload={vi.fn()}/>);
  expect(within(screen.getByRole('table',{name:'Joint calls · Combined target'})).getByText('7')).toBeVisible();
  expect(within(screen.getByRole('table',{name:'Joint calls · Unresolved copy'})).getByText('Not assessable')).toBeVisible();
  expect(screen.getByText('NO_BACKEND_EVIDENCE')).toBeVisible();
});
