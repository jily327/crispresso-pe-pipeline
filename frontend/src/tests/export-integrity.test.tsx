import {render,screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {beforeEach,expect,it,vi} from 'vitest';
import {ExportIntegrity} from '../components/ExportIntegrity';
const calls=vi.hoisted(()=>({api:vi.fn()}));
vi.mock('../api/client',()=>({api:calls.api}));
beforeEach(()=>calls.api.mockReset());
it('separates optional export warnings from authoritative lifecycle status',async()=>{
  calls.api.mockResolvedValue({state:'MISSING',message:'Excel summary is not present.',warning:'Scientific analysis completed. Optional Excel export failed.'});
  render(<ExportIntegrity workspaceId="verified"/>);
  expect(await screen.findByText(/Scientific analysis completed/)).toBeVisible();
  expect(screen.getByText(/Scientific verification is independent/)).toBeVisible();
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
  expect(calls.api).toHaveBeenCalledWith('workspaces/verified/export');
});
it('refreshes changed export bytes without declaring scientific failure',async()=>{
  calls.api.mockResolvedValueOnce({state:'UNCHANGED',message:'Workbook bytes match the generated export.',warning:null})
    .mockResolvedValue({state:'CHANGED',message:'Workbook bytes changed.',warning:null});
  render(<ExportIntegrity workspaceId="verified"/>);
  await screen.findByText('Workbook bytes match the generated export.');
  await userEvent.setup().click(screen.getByRole('button',{name:'Check summary integrity'}));
  expect(await screen.findByText('Workbook bytes changed.')).toBeVisible();
  expect(screen.queryByText('FAILED')).not.toBeInTheDocument();
});
it('does not advertise a PE export for nuclease results',async()=>{
  calls.api.mockResolvedValue({state:'NOT_APPLICABLE',message:'Not applicable',warning:null});
  const {container}=render(<ExportIntegrity workspaceId="nuclease"/>);
  await vi.waitFor(()=>expect(container).toBeEmptyDOMElement());
});
