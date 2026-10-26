"""Auditor-owned recovery identity, independent of future candidate hashing helpers."""
import argparse
from pathlib import Path
from common import ancestors,read,inventory,record,digest,write
from force_oracle import from_plan

def capture(workspace,software,backend,families=(),lease_paths=()):
    root=ancestors(workspace)
    plan=read(root/'workflow/plan.json')
    if Path(plan['output'])!=root:raise ValueError('Relocated/foreign plan')
    forced=from_plan(plan,families)
    tree=inventory(root,False)
    sources={k:{'recorded':v,'actual':record(ancestors(v['source_path']),False)} for k,v in sorted(plan['inputs'].items())}
    archive=plan['normalized_options'].get('external_demux')
    state=dict(schema='independent-recovery-identity-v1',workspace=str(root),workspace_inventory=tree,
        workflow_plan=plan,sources=sources,external_m2_inventory=inventory(archive,False) if archive else None,
        current_software=software,current_backend=backend,
        backend_executable=record(ancestors(backend['executable']),False),
        requested_force=forced['requested'],closure=forced['closure'],owned_outputs=forced['owned_outputs'],
        sibling_workflow_lock=record(root.with_name('.'+root.name+'.m7-lock'),False),
        host_leases={str(ancestors(Path(p).parent)/Path(p).name):record(p,False) for p in sorted(lease_paths)})
    # Reject concurrent mutation instead of blessing a torn capture.
    if inventory(root,False)!=tree:raise ValueError('Workspace changed during identity capture')
    for k,v in sources.items():
        if record(ancestors(v['recorded']['source_path']),False)!=v['actual']:raise ValueError('Source changed during identity capture')
    if archive and inventory(archive,False)!=state['external_m2_inventory']:raise ValueError('Archive changed during identity capture')
    if record(ancestors(backend['executable']),False)!=state['backend_executable']:raise ValueError('Backend changed during identity capture')
    if record(root.with_name('.'+root.name+'.m7-lock'),False)!=state['sibling_workflow_lock']:raise ValueError('Lock changed during identity capture')
    for p,v in state['host_leases'].items():
        if record(p,False)!=v:raise ValueError('Lease changed during identity capture')
    return dict(identity_sha256=digest(state),state=state)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('workspace');p.add_argument('--software',required=True);p.add_argument('--backend',required=True)
    p.add_argument('--force',action='append',default=[]);p.add_argument('--lease',action='append',default=[]);p.add_argument('--previous');p.add_argument('--out',required=True)
    a=p.parse_args();value=capture(a.workspace,read(a.software),read(a.backend),a.force,a.lease)
    if a.previous:value['previous_still_current']=read(a.previous)['identity_sha256']==value['identity_sha256']
    write(a.out,value)
