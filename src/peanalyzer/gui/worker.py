"""Fixed local worker. All science remains in the canonical workflow executor."""
import argparse
import hashlib
import json
import os
import sys
from peanalyzer.cli import sigterm_cleanup
from peanalyzer.gui.execution import ExecutionSpec, revalidate_execution, materialize, bind_plan
from peanalyzer.workflow import build_workflow_plan, execute_workflow, verify_workflow_output
from peanalyzer.workflow_storage import canonical


def run(spec, emit):
    refs=revalidate_execution(spec)
    emit(dict(status='WORKER_READY'))
    options=materialize(spec,refs)
    plan=build_workflow_plan(**options)
    bind_plan(spec,plan)
    revalidate_execution(spec)
    execute_workflow(**options,expected_plan=plan,expected_output_parent=spec.output_parent_identity,
        argv=['gui-run',spec.job_id,'--review-plan',spec.plan_identity_sha256,
              '--review-science',spec.scientific_identity_sha256,'--execution-spec',
              hashlib.sha256(canonical(spec.model_dump()).encode()).hexdigest()],observer=emit)
    verify_workflow_output(spec.output)
    emit(dict(status='VERIFIED_SUCCESS'))


def main():
    parser=argparse.ArgumentParser(description='Private PEAnalyzer GUI worker')
    parser.add_argument('--events-fd',type=int,required=True)
    args=parser.parse_args()
    with os.fdopen(args.events_fd,'w',buffering=1) as stream:
        def emit(event):
            try:stream.write(json.dumps(event,separators=(',',':'))+'\n')
            except (OSError,ValueError):pass  # Observation never changes scientific execution.
        def action():
            try:
                with sigterm_cleanup():
                    envelope=json.load(sys.stdin)
                    payload=envelope['spec']
                    if hashlib.sha256(canonical(payload).encode()).hexdigest()!=envelope['sha256']:
                        raise ValueError('Execution specification checksum mismatch')
                    if payload.get('intent')=='recovery':
                        from peanalyzer.gui.recovery import RecoveryExecution, run_recovery
                        run_recovery(RecoveryExecution.model_validate(payload),emit)
                    else:
                        run(ExecutionSpec.model_validate(payload),emit)
                return 0
            except BaseException as exc:
                emit(dict(status='WORKER_ERROR',code=getattr(exc,'code','WORKER_FAILED'),
                    stage_id=getattr(exc,'stage_id',None),message=str(exc)))
                return 1
        if 'PEANALYZER_SUPERVISOR_PARENT' in os.environ:
            from peanalyzer.gui.supervision import supervise
            return supervise(action,emit,int(os.environ['PEANALYZER_SUPERVISOR_PARENT']),
                int(os.environ['PEANALYZER_SUPERVISOR_PARENT_START']))
        return action()
    return 0


if __name__=='__main__':
    raise SystemExit(main())
