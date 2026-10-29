import {render,screen,waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {beforeEach,expect,it,vi} from 'vitest';
import {SetupWizard} from '../pages/SetupWizard';
const calls=vi.hoisted(()=>({api:vi.fn(),upload:vi.fn(),sampleTemplate:vi.fn()}));
vi.mock('../api/client',()=>({...calls,ViewerFailure:class extends Error{}}));
const sample={sample_name:'leaf1',barcode_id:'4A',forward_barcode:'ACGT',reverse_barcode:'TGCA',editor:'PE',treatment:'t',dpi:'6',biological_replicate:'1',paired:false,block_id:''};
let saved:any;
beforeEach(()=>{
  vi.clearAllMocks();calls.sampleTemplate.mockResolvedValue(undefined);vi.spyOn(window,'confirm').mockReturnValue(true);
  saved={draft_id:'draft',revision:0,content:{analysis_name:'',input_mode:'run',r1:null,r2:null,demux:null,samples:[],analysis_mode:null,targets:[],library_profile:'qi_hitom_v1',trim_r1:'',trim_r2:'',output_root:null,workspace_name:''},validation:null};
  calls.api.mockImplementation(async(path,body,method)=>{
    if(path==='setup/capabilities')return {files:[],run_available:false};
    if(path==='drafts')return structuredClone(saved);
    if(method==='PATCH'){saved={...saved,revision:saved.revision+1,content:body.content};return saved}
    if(path.endsWith('/validate'))return {revision:saved.revision,status:'INVALID',issues:[],targets:[],preview:null};
  });
});
it('uses File bytes, registers each mate, and replaces only after success',async()=>{
  render(<SetupWizard/>);const user=userEvent.setup();await screen.findByLabelText('Analysis name');
  const first=new File(['bytes'],'same.fastq.gz');
  calls.upload.mockResolvedValue({file_id:'r1',label:'same.fastq.gz',kind:'fastq',origin:'upload',size_bytes:'5',sha256:'hash'});
  await user.upload(screen.getByLabelText('Browse R1 FASTQ'),first);
  expect(calls.upload).toHaveBeenCalledWith('setup/uploads/fastq?filename=same.fastq.gz',first,'application/octet-stream');
  expect(screen.getByLabelText('Pool R1')).toHaveValue('r1');
  calls.upload.mockRejectedValueOnce(Error('partial upload'));
  await user.upload(screen.getByLabelText('Replace R1 FASTQ'),new File(['bad'],'bad.fastq.gz'));
  expect(screen.getByLabelText('Pool R1')).toHaveValue('r1');expect(await screen.findByRole('alert')).toHaveTextContent('partial upload');
  calls.upload.mockResolvedValue({file_id:'r2',label:'same.fastq.gz',kind:'fastq',origin:'upload',size_bytes:'5',sha256:'hash'});
  await user.upload(screen.getByLabelText('Browse R2 FASTQ'),first);expect(screen.getByLabelText('Pool R2')).toHaveValue('r2');
  expect(calls.api.mock.calls.some(([p])=>p==='jobs')).toBe(false);
});
it('downloads and imports into editable rows then uses existing validation',async()=>{
  render(<SetupWizard/>);const user=userEvent.setup();await screen.findByLabelText('Analysis name');
  await user.click(screen.getByRole('button',{name:'Download Excel template'}));expect(calls.sampleTemplate).toHaveBeenCalledOnce();
  const file=new File(['xlsx'],'samples.xlsx');calls.upload.mockResolvedValue({samples:[sample],imported_count:1,valid_count:1,warnings:[],errors:[]});
  await user.upload(screen.getByLabelText('Import Excel template'),file);expect(await screen.findByLabelText('Sample name')).toHaveValue('leaf1');
  await user.clear(screen.getByLabelText('Sample name'));await user.type(screen.getByLabelText('Sample name'),'edited');
  await user.click(screen.getByRole('button',{name:'Validate draft'}));await waitFor(()=>expect(saved.content.samples[0].sample_name).toBe('edited'));
  expect(calls.api.mock.calls.some(([p])=>p.endsWith('/validate'))).toBe(true);expect(calls.api.mock.calls.some(([p])=>p==='jobs')).toBe(false);
});
it('reports workbook row errors without replacing manual rows',async()=>{
  render(<SetupWizard/>);const user=userEvent.setup();await screen.findByLabelText('Analysis name');await user.click(screen.getByRole('button',{name:'Add sample'}));await user.type(screen.getByLabelText('Sample name'),'manual');
  calls.upload.mockResolvedValue({samples:[],imported_count:0,valid_count:0,warnings:[],errors:[{row:7,field:'barcode_id',message:'9Z is not present in the qualified catalog.'}]});
  await user.upload(screen.getByLabelText('Import Excel template'),new File(['bad'],'samples.xlsx'));
  expect(await screen.findByRole('alert')).toHaveTextContent('Row 7 · barcode_id');expect(screen.getByLabelText('Sample name')).toHaveValue('manual');
});
