# Studied authorities and immutable source map

Only exact main and the explicitly authorized prior artifact ref were fetched. No future M11C ref was listed, resolved, fetched or inspected. Main SHA: `a1f2fbb5794dfa7be3d5bc614db3baf30f6fb503`. Prior prep SHA: `5b89009d460eab76b08574664e5c7340684c808a`.

| Authority | Contracts studied |
|---|---|
| [src/peanalyzer/workflow.py](https://github.com/jily327/crispresso-pe-pipeline/blob/a1f2fbb5794dfa7be3d5bc614db3baf30f6fb503/src/peanalyzer/workflow.py) | planning (Core version probe), stages, snapshots, software identity, force closure, invalidation, resume/reuse, final verifier |
| [src/peanalyzer/workflow_storage.py](https://github.com/jily327/crispresso-pe-pipeline/blob/a1f2fbb5794dfa7be3d5bc614db3baf30f6fb503/src/peanalyzer/workflow_storage.py) | strict JSON, path ownership/no symlinks, atomic manifests, artifact inventories |
| [src/peanalyzer/workflow_models.py](https://github.com/jily327/crispresso-pe-pipeline/blob/a1f2fbb5794dfa7be3d5bc614db3baf30f6fb503/src/peanalyzer/workflow_models.py) | plan, stage and workflow manifest schemas |
| [src/peanalyzer/gui/jobs.py](https://github.com/jily327/crispresso-pe-pipeline/blob/a1f2fbb5794dfa7be3d5bc614db3baf30f6fb503/src/peanalyzer/gui/jobs.py) | acceptance identity, in-memory slot, process group supervision, cancellation, reaping and publication |
| [src/peanalyzer/gui/worker.py](https://github.com/jily327/crispresso-pe-pipeline/blob/a1f2fbb5794dfa7be3d5bc614db3baf30f6fb503/src/peanalyzer/gui/worker.py) | fixed envelope, authoritative worker revalidation/executor/verifier |
| [src/peanalyzer/gui/execution.py](https://github.com/jily327/crispresso-pe-pipeline/blob/a1f2fbb5794dfa7be3d5bc614db3baf30f6fb503/src/peanalyzer/gui/execution.py) | runtime settings, destination/source identity, materialization, Review-to-plan binding |
| [src/peanalyzer/gui/workspace.py](https://github.com/jily327/crispresso-pe-pipeline/blob/a1f2fbb5794dfa7be3d5bc614db3baf30f6fb503/src/peanalyzer/gui/workspace.py) | M10 register_completed, full verify/snapshot/projection, mutation eviction |
| [src/peanalyzer/gui/app.py](https://github.com/jily327/crispresso-pe-pipeline/blob/a1f2fbb5794dfa7be3d5bc614db3baf30f6fb503/src/peanalyzer/gui/app.py) | existing token/Host APIs and server lifespan close |
| [src/peanalyzer/cli.py](https://github.com/jily327/crispresso-pe-pipeline/blob/a1f2fbb5794dfa7be3d5bc614db3baf30f6fb503/src/peanalyzer/cli.py) | SIGTERM cleanup authority |
| [docs/m11b-run-lifecycle.md](https://github.com/jily327/crispresso-pe-pipeline/blob/a1f2fbb5794dfa7be3d5bc614db3baf30f6fb503/docs/m11b-run-lifecycle.md) | M11B supported new-run/process model and deferred recovery |
| [docs/validation/m11b/README.md](https://github.com/jily327/crispresso-pe-pipeline/blob/a1f2fbb5794dfa7be3d5bc614db3baf30f6fb503/docs/validation/m11b/README.md) | final merged M11B scientific/process/race/regression evidence and limitations |

Exact bytes and symbol line numbers are in [evidence/authorities.json](evidence/authorities.json). Key workflow boundaries: build_workflow_plan:79; execute_stage:345; _snapshots:402; force_closure:418; _invalidate:454; _validate_completed:485; verify_workflow_output:520; execute_workflow:557; resume_workflow:698. `_manifest_csv` only constructs an in-memory expected CSV during validation and is therefore allowed by pure inspection; its write occurs in execute_stage, which is forbidden.

Prior independent authorities studied: README, SOURCE_MAP, M11B_AUDIT_PLAN, M11B_CANCELLATION_ORACLE, M11B_DIRECT_GUI_ORACLE, M11B_TRIPWIRE_SPEC and adapter checklist. The prior direct/GUI comparison and cancellation ownership rules were used to preserve scientific boundaries. This preparation expands the previously explicit INFO process limitations into future M11C targets, as requested; it does not retroactively fail M11B.
