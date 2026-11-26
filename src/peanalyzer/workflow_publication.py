"""Metrics publication transaction; no scientific calculation or recursive cleanup.

Attempts live beside the workspace on the same filesystem. Failed/crashed
attempts are retained as private diagnostics, never adopted or deleted by resume.
An authenticated, complete inventory precedes the exclusive directory rename,
so a crash between rename and stage completion can be explicitly forced safely.
"""
import ctypes
import errno
import os
from pathlib import Path
import tempfile

from peanalyzer.backend.pooled import resolve_executable
from peanalyzer.workflow_storage import WorkflowError, atomic_json, inventory, owned, no_symlinks
from peanalyzer.workflow_integrity import authenticate, binding


def rename_exclusive(source, destination):
    # Linux/WSL renameat2 closes the exists-check/rename overwrite race. Fail
    # closed on unsupported hosts/filesystems instead of replacing a directory.
    libc=ctypes.CDLL(None,use_errno=True)
    rename=getattr(libc,'renameat2',None)
    if rename is None:raise WorkflowError('ATOMIC_PUBLICATION_UNAVAILABLE','renameat2 is required on Linux/WSL')
    if rename(-100,os.fsencode(source),-100,os.fsencode(destination),1):
        code=ctypes.get_errno()
        if code==errno.EEXIST:raise WorkflowError('OUTPUT_EXISTS','Metrics destination appeared during publication')
        raise OSError(code,os.strerror(code))


def publish_metrics(plan,node,runner,**kwargs):
    from peanalyzer.workflow import validate_stage
    from peanalyzer.analysis_verify import verify_analysis_output
    root=Path(plan.output)
    # Check every sample before the first backend invocation. No implicit sample
    # exclusion and no zero-valued measurement; changing the sheet needs Review.
    from peanalyzer.schemas import pcr_control_role
    from peanalyzer.sample_qc import write_empty_control, depth_assessment
    verified=verify_analysis_output(root/'analysis')
    prepared=verified.manifest['samples']
    roles={s['barcode_id']:s.get('sample_role','experimental') for s in plan.samples}
    empty=[s for s in plan.expected_samples if prepared[s]['pairs']==0 and not pcr_control_role(roles[s])]
    if empty:
        raise WorkflowError('EMPTY_SAMPLES','EMPTY_EXPERIMENTAL_SAMPLE. Zero prepared read pairs for barcode/sample IDs: '+', '.join(empty)+
            '. Check barcode orientation and input reads in Setup/Review. Correct the inputs or explicitly remove failed wells and start a new workspace; no samples were omitted.',node.stage_id)
    destination=owned(root,node.output_path)
    destination.parent.mkdir(parents=True,exist_ok=True)
    attempt=Path(tempfile.mkdtemp(prefix='.'+root.name+'.metrics-attempt-',dir=root.parent))
    output=attempt/'output'
    # Deliberately no recursive failure cleanup: an external program can create
    # arbitrary content, and an interrupted attempt has no authenticated inventory.
    count=prepared[node.sample_id]['pairs']
    if count==0:
        write_empty_control(verified, output, sample_role=roles[node.sample_id], **kwargs)
    else:
        core = resolve_executable(plan.backend_identity.executable)
        runner(output=output,core=core,**kwargs)
    native_contract = plan.normalized_options.get('native_runs_contract') == 'native-runs-v1'
    if native_contract:
        from peanalyzer.backend.native_runs import write_native_runs
        write_native_runs(output, node.sample_id, node.target_name, kwargs['targets'], prepared[node.sample_id])
    if native_contract or 'min_prepared_pairs_qc' in plan.normalized_options:
        from peanalyzer.result_dispatch import metric_model
        from peanalyzer.workflow_storage import read_json
        raw=read_json(output/'result.json')
        result=metric_model(raw).model_validate(raw)
    if 'min_prepared_pairs_qc' in plan.normalized_options:
        atomic_json(output/'sample_qc.json',depth_assessment(node.sample_id,roles[node.sample_id],count,
            plan.normalized_options['min_prepared_pairs_qc'],result))
    if native_contract:
        from peanalyzer.measurement_exports import write_measurement_exports
        write_measurement_exports(output, result)
    validate_stage(plan,node,'COMPLETED',output_override=output)
    records=[a.model_copy(update={'path':node.output_path+a.path[len('output'):]}) for a in inventory(attempt,'output')]
    integrity=authenticate(root,plan)
    identity=binding(output);identity['path']=str(destination)
    record=dict(version=1,node=node.model_dump(),directory=identity,output_artifacts=[a.model_dump() for a in records])
    # One atomic authenticated record: there is no unsigned sidecar/receipt gap.
    integrity.publications[node.stage_id]=record
    integrity.save()
    # Recheck the complete candidate after recording it and before publication.
    if records!=[a.model_copy(update={'path':node.output_path+a.path[len('output'):]}) for a in inventory(attempt,'output')]:
        raise WorkflowError('RECOVERY_PLAN_CHANGED','Metrics candidate changed during publication',node.stage_id)
    no_symlinks(destination)
    rename_exclusive(output,destination)
    # Empty-directory removal cannot delete planted content. Leave it if a file
    # appeared; it remains outside the scientific workspace and recovery scope.
    try:attempt.rmdir()
    except OSError:pass
