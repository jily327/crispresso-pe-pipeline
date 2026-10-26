"""Read-only viewer test instrumentation; fixture setup precedes executor guards."""
from pathlib import Path
import hashlib
import importlib
from peanalyzer.workflow_models import Plan
from peanalyzer.workflow_storage import read_json


def fingerprint(root):
    root=Path(root)
    files={}
    for p in sorted(root.rglob('*')):
        key=p.relative_to(root).as_posix()
        files[key]=(hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns) if p.is_file() else 'directory'
    plan=Plan.model_validate(read_json(root/'workflow/plan.json'))
    for item in plan.inputs.values():
        p=Path(item.source_path)
        files['input:'+str(p)]=(hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns)
    return files


def forbid_execution(monkeypatch):
    calls=[]
    def forbidden(*a,**k):
        calls.append('unexpected scientific execution')
        raise AssertionError('Viewer called a scientific executor or backend probe')
    targets={
      'peanalyzer.workflow':['execute_workflow','resume_workflow','build_workflow_plan','execute_stage','resolve_executable','demultiplex','prepare_analysis_fastqs','route_analysis','run_metrics','run_nuclease_metrics','summarize','stats','generate_report'],
      'peanalyzer.demux':['demultiplex'], 'peanalyzer.analysis_fastq':['prepare_analysis_fastqs'],
      'peanalyzer.routing':['route_analysis'], 'peanalyzer.metrics.production':['run_metrics'],
      'peanalyzer.nuclease.backend':['run_nuclease_metrics'], 'peanalyzer.aggregation':['summarize'],
      'peanalyzer.statistics':['stats'], 'peanalyzer.reporting':['generate_report'],
      'peanalyzer.backend.pooled':['resolve_executable'],
    }
    for module,names in targets.items():
        value=importlib.import_module(module)
        for name in names:monkeypatch.setattr(value,name,forbidden)
    return calls
