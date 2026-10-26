// Unit canaries for the Playwright route protocol, not a candidate browser audit.
import assert from 'node:assert/strict';
import {holdOnce} from './browser_races.mjs';
function fake() {
  const calls=[]; let handler;
  const page={route:async(m,h)=>{handler=h},unroute:async()=>{calls.push('unroute')}};
  const route={request:()=>({method:()=> 'POST',postData:()=> '{"synthetic":true}'}),
    fetch:async()=>{calls.push('fetch');return {synthetic:true}},
    continue:async()=>{calls.push('continue')},fulfill:async()=>{calls.push('fulfill')},abort:async()=>{calls.push('abort')}};
  return {page,route,calls,dispatch:()=>handler(route)};
}
for (const phase of ['before','after']) {
  const f=fake(),gate=await holdOnce(f.page,'**/synthetic',phase);
  const pending=f.dispatch();await gate.ready;
  assert.deepEqual(f.calls,phase==='before'?[]:['fetch']);
  gate.release();await pending;
  assert.deepEqual(f.calls,phase==='before'?['continue']:['fetch','fulfill']);
  await gate.dispose();
}
const f=fake(),gate=await holdOnce(f.page,'**/synthetic','before',10);
await assert.rejects(f.dispatch(),/audit barrier timeout/);assert.deepEqual(f.calls,['abort']);await gate.dispose();
console.log(JSON.stringify({route_protocol_canaries:3,passed:3,actual_browser_candidate_runs:0}));
