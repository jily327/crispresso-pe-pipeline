"""Independent tooling canaries; these are NOT M11B acceptance tests."""
import asyncio,copy,json,os,subprocess,sys,tempfile,threading,unittest
from pathlib import Path
from common import strict_json,digest,fields
from compare_json import compare
from filesystem_audit import inventory,changes,WriteMonitor
from event_checker import check
from race_harness import AsyncGate,ThreadGate

def events():
    rows=[dict(kind='state',state='ACCEPTED'),dict(kind='state',state='RUNNING'),
        dict(kind='stage_started',stage_id='s'),dict(kind='stage_finished',stage_id='s',status='COMPLETED',manifest_sha256='a'*64),
        dict(kind='state',state='VERIFYING'),dict(kind='verified',success=True,workflow_manifest_sha256='b'*64),
        dict(kind='processes_reaped',live_owned_processes=0),dict(kind='state',state='COMPLETED')]
    return [dict(seq=i,job_id='synthetic',**r) for i,r in enumerate(rows)]

class Tools(unittest.TestCase):
    def test_json_duplicate(self):
        with self.assertRaises(ValueError):strict_json('{"x":1,"x":2}')
    def test_json_nan(self):
        with self.assertRaises(ValueError):strict_json('{"x":NaN}')
    def test_json_overflow(self):
        with self.assertRaises(ValueError):strict_json('{"x":1e999}')
    def test_nullable_field(self):self.assertEqual(fields([dict(name='x',value=None)]),{'x':None})
    def test_exact_compare(self):self.assertFalse(compare({'x':[1,None]},{'x':[1,None]})['unexplained'])
    def test_type_attack(self):self.assertTrue(compare({'x':1},{'x':True})['unexplained'])
    def test_science_attack(self):self.assertTrue(compare({'n':12},{'n':13})['unexplained'])
    def test_explicit_waiver(self):
        w=dict(pointer='/path',left_sha256=digest('A'),right_sha256=digest('B'),reason='different owned roots',evidence='independent verified roots')
        self.assertFalse(compare({'path':'A'},{'path':'B'},[w])['unexplained'])
    def test_wildcard_waiver(self):
        with self.assertRaises(ValueError):compare({'x':1},{'x':2},[dict(pointer='/*')])
    def test_event_valid(self):self.assertEqual(check(events(),{'s':[]})['state'],'COMPLETED')
    def test_duplicate_sequence(self):
        rows=events();rows[2]['seq']=1
        with self.assertRaises(ValueError):check(rows,{'s':[]})
    def test_no_verifier(self):
        rows=events();del rows[5]
        with self.assertRaises(ValueError):check(rows,{'s':[]})
    def test_no_reap(self):
        rows=events();del rows[6]
        with self.assertRaises(ValueError):check(rows,{'s':[]})
    def test_terminal_repeat(self):
        rows=events();rows.append(dict(rows[-1],seq=8))
        with self.assertRaises(ValueError):check(rows,{'s':[]})
    def test_stage_dependency(self):
        with self.assertRaises(ValueError):check(events(),{'s':['missing']})
    def test_unknown_stage(self):
        with self.assertRaises(ValueError):check(events(),{'different':[]})
    def test_percent(self):
        rows=events();rows[1]['percent_complete']=50
        with self.assertRaises(ValueError):check(rows,{'s':[]})
    def test_cancel(self):
        rows=[dict(seq=0,job_id='j',kind='state',state='ACCEPTED'),dict(seq=1,job_id='j',kind='state',state='CANCELLING'),dict(seq=2,job_id='j',kind='processes_reaped',live_owned_processes=0),dict(seq=3,job_id='j',kind='state',state='CANCELLED')]
        self.assertEqual(check(rows,{'s':[]})['state'],'CANCELLED')
    def test_cancel_before_cleanup(self):
        rows=[dict(seq=0,job_id='j',kind='state',state='ACCEPTED'),dict(seq=1,job_id='j',kind='state',state='CANCELLED')]
        with self.assertRaises(ValueError):check(rows,{})
    def test_mutation_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'input';p.write_bytes(b'ab');before=inventory(tmp);p.write_bytes(b'ac');self.assertTrue(changes(before,inventory(tmp)))
    def test_symlink_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'link').symlink_to('/etc/passwd');self.assertEqual(inventory(p)['link']['type'],'symlink')
    def test_write_tripwire(self):
        with tempfile.TemporaryDirectory() as tmp:
            monitor=WriteMonitor();monitor.active=True
            try:
                with self.assertRaises(AssertionError):(Path(tmp)/'forbidden').write_text('no')
            finally:monitor.active=False
            self.assertFalse((Path(tmp)/'forbidden').exists())
    def test_thread_barrier(self):
        gate=ThreadGate();calls=[];t=threading.Thread(target=gate.wrap(lambda:calls.append('executed')));t.start()
        self.assertTrue(gate.entered.wait(2));self.assertEqual(calls,[]);gate.release.set();t.join(2);self.assertEqual(calls,['executed'])
    def test_async_barrier(self):
        async def run():
            gate=AsyncGate();calls=[]
            async def fn():calls.append(1)
            task=asyncio.create_task(gate.call(fn));await asyncio.wait_for(gate.entered.wait(),2)
            self.assertEqual(calls,[]);gate.release.set();await task;self.assertEqual(calls,[1])
        asyncio.run(run())
    def test_barrier_timeout(self):
        with self.assertRaises(TimeoutError):ThreadGate(.01).pause()

if __name__=='__main__':unittest.main(verbosity=2)
