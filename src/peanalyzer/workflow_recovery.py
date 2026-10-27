"""Read-only recovery preflight shared by CLI commitment and GUI inspection.

No scientific executor, executable probe, invalidation or write is called here.
Stage authority remains workflow._validate_completed and force_closure.
"""
import os
from pathlib import Path
import stat
from peanalyzer.workflow_storage import WorkflowError, no_symlinks, owned, sha, digest, load
from peanalyzer.workflow_models import Plan, StageManifest


def stored_manifests(plan):
    """Check internal identity against the stored plan, not current source/software.

    A force request cannot authorize an inconsistent ownership record. External
    drift is checked separately against the proposed plan by the reuse validator.
    """
    from peanalyzer import workflow as w
    root=Path(plan.output);refs={};records={}
    for node in plan.nodes:
        path=owned(root,w.stage_manifest_path(node))
        if not path.exists():continue
        try:
            manifest=load(path,StageManifest)
            dependencies={key:refs[key] for key in node.dependencies}
            if any(getattr(manifest,key)!=value for key,value in w._expected(plan,node,dependencies).items()):
                raise ValueError('Stored stage identity is internally inconsistent')
            # Ownership entries must remain confined to this node's output.
            for entry in manifest.output_artifacts:
                if not Path(entry.path).is_relative_to(node.output_path):
                    raise ValueError('Stage artifact escapes its output')
            records[node.stage_id]=manifest
            refs[node.stage_id]=w.dependency(root,node,manifest)
        except (ValueError,KeyError,OSError) as exc:
            raise WorkflowError('TAMPERED_STAGE_MANIFEST','Inconsistent stored manifest',node.stage_id) from exc
    return records


def check_removal_contents(root,node,manifest):
    """Refuse recursive removal of anything not covered by committed ownership."""
    path=owned(root,node.output_path)
    if not path.exists():return
    expected={owned(root,a.path) for a in manifest.output_artifacts} if manifest else set()
    directories={path} if path.is_dir() else set()
    for entry in expected:
        directories.update(p for p in entry.parents if p==path or p.is_relative_to(path))
    unknown=[]
    for entry in [path,*sorted(path.rglob('*'))] if path.is_dir() else [path]:
        no_symlinks(entry)
        if (entry.is_dir() and entry not in directories) or (not entry.is_dir() and entry not in expected):
            unknown.append(entry.relative_to(root).as_posix())
    if unknown:
        raise WorkflowError('FOREIGN_CONTENT_PRESENT','Unowned removal entries: '+', '.join(unknown),node.stage_id)


def workspace_identity(root):
    root=no_symlinks(root)
    if not root.is_dir():raise WorkflowError('INVALID_WORKSPACE','An existing workspace directory is required')
    records={}
    for path in [root,*sorted(root.rglob('*'))]:
        no_symlinks(path);s=path.stat()
        name='.' if path==root else path.relative_to(root).as_posix()
        if not (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)):
            raise WorkflowError('UNSAFE_PATH','Non-regular workspace entry: '+name)
        records[name]=dict(device=s.st_dev,inode=s.st_ino,mode=s.st_mode,mtime_ns=s.st_mtime_ns,
            size=s.st_size if path.is_file() else None,sha256=sha(path) if path.is_file() else None)
    return digest(records)


def preflight_resume(old, new, force=()):
    """Validate ALL reusable stages and deletion ownership before any mutation.

    An existing valid completion may be forced by CLI. The GUI separately directs
    completed workspaces to Open Results. Changed source/graph options retain M7
    signatures and required force-family rules; no scientific checks are relaxed.
    """
    from peanalyzer import workflow as w
    root=no_symlinks(new.output)
    if old.output!=str(root):raise WorkflowError('WORKFLOW_GRAPH_MISMATCH','Workspace was moved')
    before=workspace_identity(root)
    manifests=stored_manifests(old)
    w._graph_change(old,new,force);w._check_execution_scope(new);w.verify_inputs(new.inputs)
    for item in old.inputs.values():
        if item.snapshot:
            path=owned(root,item.snapshot)
            if not path.is_file() or sha(path)!=item.sha256:
                raise WorkflowError('SNAPSHOT_CORRUPTED',item.snapshot)
    selected=w.force_closure(new,force)
    old_selected=w.force_closure(old,force)
    removals={n.stage_id:n for p,chosen in ((old,old_selected),(new,selected)) for n in p.nodes if n.stage_id in chosen}
    all_nodes={n.stage_id:n for p in (old,new) for n in p.nodes}
    allowed={owned(root,w.stage_manifest_path(n)) for n in all_nodes.values()}
    if set(owned(root,'workflow/stages').glob('*.json'))-allowed:
        raise WorkflowError('STAGE_INVENTORY_MISMATCH','Unexpected stage completion records')
    for n in removals.values():
        path=owned(root,n.output_path);owned(root,w.stage_manifest_path(n))
        for plan in (old,new):
            if any(Path(i.source_path)==path or Path(i.source_path).is_relative_to(path) for i in plan.inputs.values()):
                raise WorkflowError('EXTERNAL_INPUT_PROTECTION','Recovery would remove an original source')
        check_removal_contents(root,n,manifests.get(n.stage_id))
    refs={};stages=[]
    for node in new.nodes:
        manifest=owned(root,w.stage_manifest_path(node));output=owned(root,node.output_path)
        state='RERUN' if node.stage_id in selected else 'RUN'
        reasons=[]
        if node.stage_id in selected:
            reasons=['FORCED_FAMILY:'+('all' if 'all' in force else node.stage_kind)] if node.stage_kind in force or 'all' in force else ['DEPENDS_ON:'+key for key in node.dependencies if key in selected] or ['SOURCE_FOR:demux']
        elif manifest.exists():
            if any(k not in refs for k in node.dependencies):
                raise WorkflowError('STALE_STAGE_IDENTITY','Completed stage depends on unavailable completion',node.stage_id)
            result=w._validate_completed(new,node,{k:refs[k] for k in node.dependencies})
            refs[node.stage_id]=w.dependency(root,node,result);state='REUSE';reasons=list(result.reason_codes)
        elif output.exists():
            raise WorkflowError('ORPHANED_STAGE_OUTPUT',node.output_path,node.stage_id)
        stages.append(dict(stage_id=node.stage_id,stage_kind=node.stage_kind,action=state,
            output_path=node.output_path,reason_codes=reasons))
    after=workspace_identity(root)
    if before!=after:raise WorkflowError('RECOVERY_PLAN_CHANGED','Workspace changed during preflight')
    return dict(workspace_identity=after,workflow_identity=digest(new),force=sorted(set(force)),
        closure=[n.stage_id for n in new.nodes if n.stage_id in selected],stages=stages,
        removal_paths=sorted({path for n in removals.values() for path in (n.output_path,w.stage_manifest_path(n))} | ({'workflow_manifest.json'} if force and owned(root,'workflow_manifest.json').exists() else set())),
        software_identity=new.software_identity.model_dump(),backend_identity=new.backend_identity.model_dump())


def options_from_plan(plan, *, crispresso=None, runtime_digest=None):
    """Reconstruct only canonical M7 options, never commands from a browser."""
    roles={'samples':'samples','targets':'targets','config':'config','barcodes':'barcodes','contrasts':'contrasts','policies':'tolerance_policies'}
    options={arg:Path(plan.inputs[role].source_path) for role,arg in roles.items() if role in plan.inputs}
    options.update(mode=plan.mode,output=Path(plan.output),crispresso=crispresso or plan.backend_identity.executable,
        runtime_digest=runtime_digest or plan.backend_identity.runtime_digest,title=plan.normalized_options['title'])
    prep=plan.normalized_options['preparation']
    options.update(analysis_r1_trim_5p=prep['r1_analysis_trim_5p'],analysis_r2_trim_5p=prep['r2_analysis_trim_5p'])
    if plan.mode=='run':options.update(r1=Path(plan.inputs['r1'].source_path),r2=Path(plan.inputs['r2'].source_path))
    else:options['demux_root']=Path(plan.normalized_options['external_demux'])
    return options
