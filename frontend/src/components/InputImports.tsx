import {useEffect,useRef,useState} from 'react';
import {sampleTemplate,upload,ViewerFailure} from '../api/client';
import type {DraftSample,SetupFile,WorkbookImport} from '../models/setup';

export function InputImports({profile,raw,disabled,onUploaded,onSamples,onBusy,selected}:{
  profile:'qi_hitom_v1'|'custom';raw:boolean;disabled:boolean;
  onUploaded:(role:'r1'|'r2',file:SetupFile)=>void;onSamples:(rows:DraftSample[])=>void;
  onBusy:(busy:boolean)=>void;selected:{r1?:SetupFile;r2?:SetupFile};
}) {
  const [error,setError]=useState(''),[message,setMessage]=useState(''),[result,setResult]=useState<WorkbookImport|null>(null);
  const active=useRef(true),inflight=useRef(false);
  useEffect(()=>{active.current=true;return()=>{active.current=false}},[]);
  const explain=(e:unknown)=>e instanceof ViewerFailure?`${e.detail.code}: ${e.detail.detail}`:String(e);
  async function receive(role:'r1'|'r2',file?:File){
    if(!file||inflight.current)return;inflight.current=true;onBusy(true);setError('');setMessage(`Uploading ${role.toUpperCase()}…`);
    try{const entry=await upload<SetupFile>(`setup/uploads/fastq?filename=${encodeURIComponent(file.name)}`,file,'application/octet-stream');
      if(active.current){onUploaded(role,entry);setMessage(`${role.toUpperCase()}: ${entry.label} · ${entry.size_bytes} bytes · Registered`)}}
    catch(e){if(active.current){setError(explain(e));setMessage('Upload failed. Previous input selection is unchanged.')}}
    finally{inflight.current=false;if(active.current)onBusy(false)}
  }
  async function workbook(file?:File){
    if(!file||inflight.current)return;
    if(!file.name.toLowerCase().endsWith('.xlsx')){setError('Select the official .xlsx template; .xls and .xlsm are unsupported.');return}
    if(!window.confirm('A valid import replaces the current sample rows. Review the imported rows before Run. Continue?'))return;
    inflight.current=true;onBusy(true);setError('');setResult(null);setMessage('Validating Excel sample rows…');
    try{const value=await upload<WorkbookImport>(`setup/samples/import?profile=${profile}`,file,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      if(active.current){setResult(value);setMessage(`${value.imported_count} samples imported · ${value.valid_count} valid · ${value.warnings.length} warnings · ${value.errors.length} errors`);if(!value.errors.length)onSamples(value.samples)}}
    catch(e){if(active.current){setError(explain(e));setMessage('Import failed. Current sample rows are unchanged.')}}
    finally{inflight.current=false;if(active.current)onBusy(false)}
  }
  return <section aria-label="Browser input transfer"><h3>Choose local files</h3>
    {raw&&<><p>Browse on this computer to upload bytes. No Windows-to-Linux path conversion is needed. Launcher-registered inputs remain available above.</p>
      <div className="form-grid">{(['r1','r2'] as const).map(role=><div key={role}>
        <label>{selected[role]?`Replace ${role.toUpperCase()} FASTQ`:`Browse ${role.toUpperCase()} FASTQ`}<input type="file" disabled={disabled} accept=".fastq,.fq,.fastq.gz,.fq.gz" onChange={e=>{const file=e.target.files?.[0];e.target.value='';void receive(role,file)}}/></label>
        {selected[role]&&<p>{selected[role]!.label}{selected[role]!.size_bytes!=null&&` · ${selected[role]!.size_bytes} bytes`} · Registered</p>}
      </div>)}</div><p>Completed uploads are durable original sources. Keep the upload storage in place for verification and recovery. Replacement does not delete earlier inputs.</p></>}
    <h3>Sample spreadsheet</h3><p>Import profile: {profile==='qi_hitom_v1'?'QI-HITOM v1 qualified catalog':'Custom barcodes at read start'}. Change the library profile in Configuration if needed. Numeric dpi is required; no value is inferred.</p>
    <button disabled={disabled} onClick={()=>void sampleTemplate().catch(e=>setError(explain(e)))}>Download Excel template</button>
    <label>Import Excel template<input type="file" disabled={disabled} accept=".xlsx" onChange={e=>{const file=e.target.files?.[0];e.target.value='';void workbook(file)}}/></label>
    {message&&<p role="status">{message}</p>}{error&&<p role="alert">{error}</p>}
    {!!result?.errors.length&&<div role="alert"><p>No sample rows were replaced. Correct these cells and import again.</p><ul>{result.errors.map((e,i)=><li key={i}>Row {e.row||'workbook'} · {e.field}: {e.message}</li>)}</ul></div>}
    <p>Import never starts science. Imported rows remain editable and require Validate &amp; Review.</p>
  </section>;
}
