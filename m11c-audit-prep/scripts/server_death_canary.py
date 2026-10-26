"""Baseline-only negative control: kill/restart real JobStore server processes."""
import argparse,os,signal,subprocess,sys
from pathlib import Path
from common import write,read,baseline_import
from process_fixture import wait
from proc_oracle import identity,birth,census,subreaper,cleanup

def run(checkout,fixtures,output):
    baseline_import(checkout);subreaper();root=Path(output);root.mkdir(parents=True,exist_ok=False)
    known=[];servers=[];logs=[];result={}
    canary=subprocess.Popen([sys.executable,str(Path(__file__).with_name('process_fixture.py')),str(root/'canary'),'--role','canary','--token','unrelated'],start_new_session=True)
    canary_birth=identity(canary.pid)
    try:
        for name in ('before-restart','after-restart'):
            folder=root/name;log=(root/(name+'.log')).open('w');logs.append(log)
            p=subprocess.Popen([sys.executable,str(Path(__file__).with_name('server_fixture.py')),'--baseline',checkout,'--fixtures',fixtures,'--output',str(folder)],start_new_session=True,stdout=log,stderr=subprocess.STDOUT);servers.append(p);known.append(identity(p.pid))
            wait(folder/'accepted.json')
            tree=[read(folder/'tree'/(role+'-ready.json'))['identity'] for role in ('worker','child','grandchild')];known.extend(tree)
            result[name]=dict(accepted=read(folder/'accepted.json'),tree=tree,server=identity(p.pid))
            if name=='before-restart':
                p.kill();p.wait(timeout=5)
                result['after_server_sigkill']=census(tree)
                assert all(v['live'] for v in result['after_server_sigkill'])
        workers=[result[k]['tree'][0] for k in ('before-restart','after-restart')]
        assert all(v['live'] for v in census(workers))
        assert birth(identity(canary.pid))==birth(canary_birth)
        result.update(baseline_two_live_workers_reproduced=True,unrelated_canary_survives=True,
            limitation='TestClient transport; fixed synthetic worker tree replaces scientific run; auditor subreaper adopts orphans, not PID 1; no candidate tested',
            expected_M11C='Restart remains BUSY while any prior owned scientific worker or descendant is live')
    finally:
        # Discover fixture births even after a readiness failure, before own-birth cleanup.
        for path in root.glob('*/tree/*-ready.json'):
            value=read(path)['identity']
            if not any(birth(v)==birth(value) for v in known):known.append(value)
        cleanup(known)
        for p in servers:p.wait(timeout=5)
        cleanup([canary_birth]);canary.wait(timeout=5)
        for log in logs:log.close()
    result['all_known_fixture_births_reaped']=True;write(root/'server-death.json',result)
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--baseline',required=True);p.add_argument('--fixtures',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.baseline,a.fixtures,a.output);print('Server hard-kill/restart negative control verified; fixture births reaped')
