import type { ErrorDetail } from '../models/api';
export class ViewerFailure extends Error {
  constructor(public detail: ErrorDetail) { super(detail.message); }
}
export function initializeToken() {
  const token = window.location.hash.slice(1);
  if (token) { sessionStorage.setItem('viewer-token', token); history.replaceState(null, '', window.location.pathname); }
}
const headers = () => ({ 'X-Viewer-Token': sessionStorage.getItem('viewer-token') || '' });
async function checked(path: string, options?: RequestInit) {
  const response = await fetch('/api/v1/' + path, { ...options, headers: { ...headers(), ...options?.headers } });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ViewerFailure(body?.error || { code: 'CONNECTION_FAILED', message: 'The local viewer could not verify this request.', detail: String(response.status), stage_id: null });
  }
  return response;
}
export async function api<T>(path: string, body?: unknown, method?: string): Promise<T> {
  const response = await checked(path, { method: method || (body === undefined ? 'GET' : 'POST'),
    ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }) });
  return response.status === 204 ? undefined as T : response.json();
}
export async function download(workspace: string, id: string, name: string) {
  const response = await checked(`workspaces/${workspace}/artifacts/${id}`);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a'); link.href = url; link.download = name.split('/').at(-1)!; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// File is the browser-selected byte source; never translate a Windows path.
export async function upload<T>(path: string, file: File, mediaType: string): Promise<T> {
  const response = await checked(path, {method:'POST',headers:{'Content-Type':mediaType},body:file});
  return response.json();
}
export async function sampleTemplate() {
  const response = await checked('setup/samples/template');
  const url=URL.createObjectURL(await response.blob());
  const link=document.createElement('a');link.href=url;link.download='PEAnalyzer-samples-v1.xlsx';link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
