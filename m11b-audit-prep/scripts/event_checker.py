"""Validate an audit-normalized event stream; adapters must retain raw evidence."""
import argparse,json,re
def valid_hash(value):return isinstance(value,str) and re.fullmatch(r"[0-9a-f]{64}",value) is not None
from common import read,strict_json
TERMINAL={'COMPLETED','FAILED','CANCELLED'}
TRANSITIONS={None:{'ACCEPTED'},'ACCEPTED':{'RUNNING','CANCELLING','FAILED','CANCELLED'},
 'RUNNING':{'CANCELLING','VERIFYING','FAILED'},'VERIFYING':{'COMPLETED','CANCELLING','FAILED'},
 'CANCELLING':{'CANCELLED','FAILED'}}

def check(events,dependencies,require_terminal=True):
    last=-1;job=None;state=None;active=None;done=set();verified=None;reaped=False;terminal=0
    for e in events:
        if terminal:raise ValueError('event after terminal transition; replay snapshots are not new events')
        n=e['seq']
        if type(n) is not int or n<=last:raise ValueError('duplicate/nonmonotonic sequence')
        last=n
        if job is None:job=e['job_id']
        if not isinstance(job,str) or not job or e['job_id']!=job:raise ValueError('mixed/invalid job identity')
        if 'percent_complete' in e:raise ValueError('unqualified percent complete; use literal stage counts')
        kind=e['kind']
        if kind=='state':
            new=e['state']
            if new not in TRANSITIONS.get(state,set()):raise ValueError('invalid state transition')
            if new=='COMPLETED' and (not verified or not reaped or set(dependencies)!=done or active):raise ValueError('unverified/incomplete/live-worker completion')
            if new in {'CANCELLED','FAILED'} and not reaped:raise ValueError('terminal failure/cancellation before process cleanup')
            if new=='RUNNING':reaped=False
            state=new;terminal+=int(new in TERMINAL)
        elif kind=='stage_started':
            stage=e['stage_id']
            if state!='RUNNING' or active or stage in done or stage not in dependencies or not set(dependencies[stage])<=done:raise ValueError('impossible stage start')
            active=stage;reaped=False
        elif kind=='stage_finished':
            if state not in {'RUNNING','CANCELLING'} or e['stage_id']!=active:raise ValueError('unmatched stage completion')
            if e['status'] not in {'COMPLETED','SKIPPED_SCIENTIFIC_GATE'}:raise ValueError('invalid stage status')
            if e['status']=='SKIPPED_SCIENTIFIC_GATE' and not e.get('reason_codes'):raise ValueError('gate without reason')
            if not valid_hash(e.get('manifest_sha256')):raise ValueError('no completion artifact identity')
            done.add(active);active=None
        elif kind=='verified':
            if state!='VERIFYING' or e.get('success') is not True or not valid_hash(e.get('workflow_manifest_sha256')):raise ValueError('false verification evidence')
            verified=e['workflow_manifest_sha256']
        elif kind=='processes_reaped':
            if state not in {'ACCEPTED','RUNNING','VERIFYING','CANCELLING'} or type(e.get('live_owned_processes')) is not int or e['live_owned_processes']!=0:raise ValueError('invalid cleanup evidence')
            reaped=True
        elif kind=='diagnostic':pass
        else:raise ValueError('unmapped event kind: '+str(kind))
    if require_terminal and terminal!=1:raise ValueError('missing unique terminal transition')
    return {'events':len(events),'state':state,'stages_finished':len(done),'terminal_transitions':terminal}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('events');p.add_argument('dependencies');a=p.parse_args()
    with open(a.events) as f:events=[strict_json(x) for x in f if x.strip()]
    print(json.dumps(check(events,read(a.dependencies)),indent=2))
