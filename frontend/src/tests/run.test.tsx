import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import { Run } from '../pages/Run';
import { Review } from '../pages/SetupWizard';
import type { JobView } from '../models/jobs';
import type { PlanPreview } from '../models/setup';
const calls=vi.hoisted(()=>({api:vi.fn()}));
vi.mock('../api/client',()=>({api:calls.api,ViewerFailure:class extends Error{}}));
let job:JobView;
beforeEach(()=>{
  calls.api.mockReset();
  HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','')};
  HTMLDialogElement.prototype.close=function(){this.removeAttribute('open')};
  job={job_contract:'analysis-job-v1',job_id:'opaque-job',draft_id:'draft',revision:3,state:'RUNNING',analysis_name:'Accepted study',analysis_mode:'indel_nuclease',target_name:'Backend target',output_proposal:'outputs / study',plan_identity_sha256:'plan',scientific_identity_sha256:'science',execution_spec_sha256:'spec',input_metadata:[],warnings:[{severity:'WARNING',code:'SCIENTIFIC_GATE',step:'target',field:'targets',message:'Copy family remains blocked',detail:null}],stages:[{stage_id:'routing::sample::T1',kind:'routing',label:'Single-copy identity check',dependencies:[],output_path:'routing/sample/T1',status:'SKIPPED_SCIENTIFIC_GATE',reason_codes:['BACKEND_REASON']}],current_stage_id:'routing::sample::T1',finished_stages:7,total_stages:19,started_at:'backend-time',ended_at:null,elapsed_seconds:123.4,cancellable:true,error:null,workspace_id:null,latest_sequence:1};
  calls.api.mockImplementation(async(path:string)=>path.includes('/events?')?{items:[{sequence:1,timestamp:'backend-time',state:'RUNNING',status:'RUNNING',stage_id:null,stage_kind:null,reason_codes:[],code:null}],next_sequence:1,has_more:false}:structuredClone(job));
});
it('displays authoritative counts, stages, warnings and identities without percentage or science',async()=>{
  render(<Run jobId="opaque-job" onOpen={vi.fn()}/>);await screen.findByRole('heading',{name:'Accepted study'});
  expect(screen.getByText(/7 \/ 19 stages finished/)).toBeVisible();expect(screen.getByText(/123.4 seconds/)).toBeVisible();
  expect(screen.getByText('SKIPPED_SCIENTIFIC_GATE')).toBeVisible();expect(screen.getByText('BACKEND_REASON')).toBeVisible();
  expect(screen.getByText(/Copy family remains blocked/)).toBeVisible();expect(screen.getByText('science')).toBeVisible();
  expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();expect(document.body.textContent).not.toContain('%');
  expect(calls.api.mock.calls.every(([path,body])=>path.startsWith('jobs/opaque-job')&&body===undefined)).toBe(true);
});
it('requires deliberate cancellation confirmation and submits no process or scientific parameters',async()=>{
  const user=userEvent.setup();render(<Run jobId="opaque-job" onOpen={vi.fn()}/>);
  await user.click(await screen.findByRole('button',{name:'Cancel analysis'}));expect(calls.api.mock.calls.some(([p])=>p.endsWith('/cancel'))).toBe(false);
  await user.click(screen.getByRole('button',{name:'Keep running'}));expect(screen.getByRole('button',{name:'Cancel analysis'})).toHaveFocus();
  await user.click(screen.getByRole('button',{name:'Cancel analysis'}));job.state='CANCELLING';job.cancellable=false;
  await user.click(screen.getByRole('button',{name:'Confirm cancellation'}));await screen.findByText(/Stopping the worker/);
  expect(calls.api).toHaveBeenCalledWith('jobs/opaque-job/cancel',{});
});
it('shows backend failure code, stage and message without fabricated results',async()=>{
  job.state='FAILED';job.cancellable=false;job.error={code:'BACKEND_REAL_CODE',stage_id:'metrics::sample::T1',message:'Backend qualification failed.',detail:'Actual backend diagnostic'};
  const user=userEvent.setup();render(<Run jobId="opaque-job" onOpen={vi.fn()}/>);await screen.findByText('Backend qualification failed.');
  await user.click(screen.getByText('Technical details'));expect(screen.getByText('Actual backend diagnostic')).toBeVisible();expect(screen.getByText(/BACKEND_REAL_CODE/)).toBeVisible();
  expect(screen.queryByRole('button',{name:'Open Results'})).not.toBeInTheDocument();
});
it('opens only the opaque verified workspace through the existing viewer callback',async()=>{
  job.state='COMPLETED';job.cancellable=false;job.workspace_id='verified-workspace';const open=vi.fn().mockResolvedValue(undefined);
  const user=userEvent.setup();render(<Run jobId="opaque-job" onOpen={open}/>);await user.click(await screen.findByRole('button',{name:'Open Results'}));
  expect(open).toHaveBeenCalledWith('verified-workspace');expect(screen.queryByRole('button',{name:'Cancel analysis'})).not.toBeInTheDocument();
});
it('reconnects to ordered prior events and state without starting another execution',async()=>{
  job.state='CANCELLING';job.cancellable=false;const {unmount}=render(<Run jobId="opaque-job" onOpen={vi.fn()}/>);
  await screen.findByText(/Stopping the worker/);unmount();render(<Run jobId="opaque-job" onOpen={vi.fn()}/>);await screen.findByText(/Stopping the worker/);
  await userEvent.setup().click(screen.getByText('Ordered job events'));expect(screen.getByText(/1 · backend-time/)).toBeVisible();
  expect(calls.api.mock.calls.every(([path,body])=>path!=='jobs'&&body===undefined)).toBe(true);
});
it.each([null,'registered output'])('Review Run requires a backend validated output: %s',async output=>{
  const plan={analysis_name:'Review',analysis_mode:'precise_edit',sample_count:'1',copy_count:'1',sample_ids:[],samples:[],inputs:[],targets:[],configuration:[],backend_identity:[],stages:[],output_proposal:output,deferred:[],scientific_identity_sha256:'science',plan_identity_sha256:'plan'} as unknown as PlanPreview;
  const run=vi.fn();render(<Review plan={plan} runAvailable onRun={run}/>);
  if(output){await userEvent.setup().click(screen.getByRole('button',{name:'Run Analysis'}));expect(run).toHaveBeenCalledOnce()}
  else expect(screen.getByRole('button',{name:'Run Analysis'})).toBeDisabled();
});
