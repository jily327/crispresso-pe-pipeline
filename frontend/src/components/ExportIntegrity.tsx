import {useEffect,useState} from 'react';
import {api} from '../api/client';
type ExportState={state:string,message:string,warning:string|null};
export function ExportIntegrity({workspaceId}:{workspaceId:string}){
  const [value,setValue]=useState<ExportState|null>(null),[error,setError]=useState('');
  const [revision,setRevision]=useState(0);
  useEffect(()=>{
    let active=true;
    async function check(){try{
      const next=await api<ExportState>(`workspaces/${workspaceId}/export`);
      if(active){setValue(next);setError('')}
    }catch{if(active)setError('Export integrity could not be checked. Reopen scientific results if verification has changed.')}}
    setValue(null);void check();const timer=setInterval(()=>void check(),10000);
    window.addEventListener('focus',check);
    return()=>{active=false;clearInterval(timer);window.removeEventListener('focus',check)};
  },[workspaceId,revision]);
  if(value?.state==='NOT_APPLICABLE')return null;
  return <section className="callout" aria-label="Excel summary integrity">
    <strong>Excel summary integrity</strong>
    <p aria-live="polite">{error||value?.message||'Checking the separate Excel export…'}</p>
    {value?.warning&&<p className="field-issues">{value.warning}</p>}
    <p>Scientific verification is independent of workbook edits and its Excel lock file.</p>
    <button onClick={()=>setRevision(r=>r+1)}>Check summary integrity</button>
  </section>;
}
