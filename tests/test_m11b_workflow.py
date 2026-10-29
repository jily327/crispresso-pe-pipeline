"""Observer byte parity and the executor's exclusive new-root boundary."""
from datetime import datetime, timezone
from pathlib import Path
import shutil
import pytest
from test_m7 import case
from peanalyzer import workflow as w


def test_observer_preserves_every_workspace_byte(case,monkeypatch):
    options,_=case
    class FrozenDate:
        @classmethod
        def now(cls,tz):return datetime(2026,1,1,tzinfo=timezone.utc)
    import peanalyzer.demux as demux
    monkeypatch.setattr(demux,'datetime',FrozenDate)
    import gzip
    monkeypatch.setattr(gzip.time,'time',lambda:1767225600.0)
    monkeypatch.setattr(w,'utc',lambda:'2026-01-01T00:00:00+00:00')
    class FixedUUID:hex='1234567890abcdef1234567890abcdef'
    monkeypatch.setattr(w.uuid,'uuid4',lambda:FixedUUID())
    from peanalyzer import workflow_integrity
    actual_binding=workflow_integrity.binding;fixed_binding=[]
    def frozen_binding(root):
        # Recreating the root changes its inode independently of observation.
        # Freeze that external input, like time/UUID, and compare EVERY byte.
        if not fixed_binding:fixed_binding.append(actual_binding(root))
        return dict(fixed_binding[0])
    monkeypatch.setattr(workflow_integrity,'binding',frozen_binding)
    snapshots=w._snapshots
    def frozen_snapshots(plan):
        import os
        snapshots(plan)
        for item in plan.inputs.values():
            if item.snapshot:os.utime(Path(plan.output)/item.snapshot,ns=(1767225600000000000,1767225600000000000))
    monkeypatch.setattr(w,'_snapshots',frozen_snapshots)
    w.execute_workflow(**options,argv=['observer-parity'])
    root=options['output']
    original={p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
    shutil.rmtree(root)
    events=[]
    def observer(event):
        events.append(dict(event))
        event['stage_id']='malicious alteration';event['reason_codes'].append('fake')
        raise RuntimeError('Presentation callback failure must not affect science')
    w.execute_workflow(**options,argv=['observer-parity'],observer=observer)
    observed={p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
    if original!=observed:
        import difflib
        differences=[]
        for name in sorted(original):
            if original[name]!=observed.get(name) and name.endswith('.json'):
                differences.append(name+'\n'+''.join(difflib.unified_diff(original[name].decode().splitlines(True),observed[name].decode().splitlines(True)))[:3500])
        pytest.fail('\n'.join(differences)[:14000])
    assert any(e['status']=='RUNNING' for e in events) and events[-1]['status']=='FINAL_VALIDATION'
    assert w.verify_workflow_output(root).status=='COMPLETED'


def test_existing_output_appearing_during_plan_is_untouched(case,monkeypatch):
    options,_=case;build=w.build_workflow_plan;root=options['output']
    def raced(**kwargs):
        plan=build(**kwargs);root.mkdir();(root/'workflow_manifest.json').write_text('foreign')
        return plan
    monkeypatch.setattr(w,'build_workflow_plan',raced)
    with pytest.raises(w.WorkflowError,match='OUTPUT_EXISTS'):w.execute_workflow(**options)
    assert (root/'workflow_manifest.json').read_text()=='foreign'
    assert list(root.iterdir())==[root/'workflow_manifest.json']
    assert not root.with_name('.'+root.name+'.m7-lock').exists()


def test_changed_bound_plan_fails_before_science(case,monkeypatch):
    options,_=case;plan=w.build_workflow_plan(**options)
    options['samples'].write_text(options['samples'].read_text().replace('bio1','different'))
    with pytest.raises(w.WorkflowError,match='ACCEPTED_PLAN_CHANGED'):w.execute_workflow(**options,expected_plan=plan)
    assert not options['output'].exists()
