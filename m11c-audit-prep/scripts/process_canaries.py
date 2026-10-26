"""Demonstrate why PGID-only and PID-only oracles are inadequate; clean only own births."""
import argparse,os,signal,subprocess,sys,time,uuid
from pathlib import Path
from common import read,write
from proc_oracle import identity,birth,census,signal_owned,subreaper,cleanup,clean_cancelled,lease_decision
from process_fixture import wait


def run(output):
    root=Path(output);root.mkdir(parents=True,exist_ok=False);subreaper();records=[]
    for mode in ('none','setsid','pgrp','late-setsid','retained-setsid'):
        folder=root/mode;folder.mkdir();known=[];token=uuid.uuid4().hex
        command=[sys.executable,str(Path(__file__).with_name('process_fixture.py')),str(folder),'--escape','setsid' if mode in ('late-setsid','retained-setsid') else mode,'--ignore-term','--token',token]
        if mode!='retained-setsid':command+=['--close-stdio']
        if mode=='late-setsid':command+=['--late-escape']
        process=subprocess.Popen(command,start_new_session=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        canary=subprocess.Popen([sys.executable,str(Path(__file__).with_name('process_fixture.py')),str(folder/'canary'),'--role','canary','--token',token],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        known.append(identity(process.pid));canary_birth=identity(canary.pid)
        try:
            wait(folder/'child-before.json');known.append(read(folder/'child-before.json')['identity'])
            if mode=='late-setsid':(folder/'release-escape').touch()
            wait(folder/'grandchild-ready.json');known.append(read(folder/'grandchild-ready.json')['identity'])
            wait(folder/'child-ready.json');ready=[read(folder/(r+'-ready.json'))['identity'] for r in ('worker','child','grandchild')]
            # This signal is restricted to the newly launched fixture session/group.
            assert ready[0]['pgid']==process.pid and birth(identity(process.pid))==birth(known[0])
            os.killpg(process.pid,signal.SIGTERM);process.wait(timeout=5)
            # Surviving child readiness proves its handler/session state, not timing guesses.
            alive=census(known[1:]);assert all(v['live'] for v in alive)
            try:clean_cancelled('CANCELLED',known,False,False)
            except AssertionError:false_cancel_rejected=True
            else:raise AssertionError('False cancellation accepted by audit oracle')
            old=dict(canary_birth,start_ticks=canary_birth['start_ticks']-1)
            assert not signal_owned(old,signal.SIGTERM) and identity(canary.pid) is not None
            assert lease_decision(known[0],None,[v['current'] for v in alive])=='BUSY'
            retained=None
            if mode=='retained-setsid':
                os.set_blocking(process.stdout.fileno(),False);retained=process.stdout.read() is None;assert retained
            records.append(dict(mode=mode,stdio_pipe_held_open=retained,before_and_ready=ready,after_group_term=census(known),
                false_cancel_rejected=false_cancel_rejected,pid_reuse_signal_refused=True,unrelated_canary_survives=True,
                audit_subreaper_adopted=True,baseline_conclusion='Group/parent disappearance alone is insufficient; not an M11C candidate verdict'))
        finally:
            for path in folder.glob('*-ready.json'):
                value=read(path)['identity']
                if not any(birth(v)==birth(value) for v in known):known.append(value)
            cleanup(known);process.wait();cleanup([canary_birth]);canary.wait()
            process.stdout.close()
            if records and records[-1]['mode']==mode:records[-1]['all_fixture_births_reaped']=True
    write(root/'process-canaries.json',records);return records

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');a=p.parse_args();print('Process modes checked:',len(run(a.output)))
