import {useState} from 'react';
import {api} from '../api/client';
export function OpenOutput({workspaceId}:{workspaceId:string}){
  const [message,setMessage]=useState(''),[busy,setBusy]=useState(false);
  return <span><button disabled={busy} onClick={async()=>{
    setBusy(true);try{const result=await api<{ok:boolean,message:string}>(`workspaces/${workspaceId}/reveal`,{});setMessage(result.message)}
    catch{setMessage('Could not open output folder. Reopen and verify the analysis before retrying.')}
    finally{setBusy(false)}
  }}>Open output folder</button><span role="status">{message}</span></span>;
}
