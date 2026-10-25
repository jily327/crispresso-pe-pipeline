"""In-memory registrations and immutable verified snapshots, outside scientific workspaces."""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
import threading
import uuid

from peanalyzer.workflow import verify_workflow_output
from peanalyzer.workflow_models import Plan, StageManifest
from peanalyzer.workflow_storage import (WorkflowError, no_symlinks, owned, read_json,
    artifact, sha, digest)
from peanalyzer.gui.artifacts import sources, read_bound
from peanalyzer.gui.models import Registration
from peanalyzer.gui.projection import project


class ViewerError(WorkflowError):
    pass


def safe_registration(path):
    raw = str(path)
    if '..' in Path(raw).parts or '\\' in raw:
        raise ViewerError('UNSAFE_PATH', 'Workspace registration cannot contain traversal')
    return no_symlinks(Path(os.path.abspath(raw)))


def snapshot(root, inputs=()):
    """Hash regular-file bytes and directory inventory; never follow symlinks/devices."""
    no_symlinks(root)
    if not root.is_dir():
        raise ViewerError('WORKSPACE_NOT_FOUND', 'Registered workspace does not exist')
    result={}
    for path in sorted(root.rglob('*')):
        no_symlinks(path)
        mode=path.stat().st_mode
        key=path.relative_to(root).as_posix()
        if stat.S_ISDIR(mode):
            result[key+'/']='directory'
        elif stat.S_ISREG(mode):
            result[key]=sha(path)
        else:
            raise ViewerError('UNSAFE_PATH', 'Workspace contains a non-regular file')
    for path in inputs:
        p=no_symlinks(path)
        if not stat.S_ISREG(p.stat().st_mode):
            raise ViewerError('UNSAFE_PATH', 'Input is not a regular file')
        result['input:'+str(p)]=sha(p)
    return result


@dataclass
class Opened:
    root: Path
    identity: dict
    inputs: list[str]
    records: dict
    view: object
    alleles: dict


class WorkspaceStore:
    def __init__(self, registrations):
        self.registrations={uuid.uuid4().hex:(label,safe_registration(path)) for label,path in registrations}
        self.opened={}
        self.lock=threading.RLock()

    def catalog(self):
        return [Registration(registration_id=k,label=v[0]) for k,v in self.registrations.items()]

    def open(self, registration_id):
        with self.lock:
            if registration_id not in self.registrations:
                raise ViewerError('UNKNOWN_REGISTRATION', 'Select a workspace registered by the local launcher')
            label,root=self.registrations[registration_id]
            initial=snapshot(root)
            if 'workflow_manifest.json' not in initial:
                raise ViewerError('INCOMPLETE_WORKSPACE', 'A completed workflow manifest is required')
            manifest=verify_workflow_output(root)
            plan=Plan.model_validate(read_json(owned(root,manifest.plan.path)))
            inputs=[a.source_path for a in plan.inputs.values()]
            identity=snapshot(root,inputs)
            if initial != {k:v for k,v in identity.items() if not k.startswith('input:')}:
                raise ViewerError('WORKSPACE_CHANGED', 'Workspace changed during verification')
            records={}
            for ref in [artifact(root,root/'workflow_manifest.json'),manifest.plan,manifest.statistics_result,
                        manifest.report_manifest,*manifest.stage_inventory.values()]:
                records[ref.path]=ref
            for ref in manifest.stage_inventory.values():
                stage=StageManifest.model_validate(json.loads(read_bound(root,ref)))
                for item in stage.output_artifacts:
                    records[item.path]=item
            inventory=sources(records)
            def read(path):
                if path not in records:
                    raise ViewerError('UNVERIFIED_ARTIFACT', 'Projection source is not inventoried')
                # Duplicate/nonfinite JSON checks remain in authoritative verification.
                return json.loads(read_bound(root,records[path]))
            workspace_id=uuid.uuid4().hex
            view,alleles=project(root,manifest,read,inventory,workspace_id,label,digest(identity))
            verify_workflow_output(root)
            if identity != snapshot(root,inputs):
                raise ViewerError('WORKSPACE_CHANGED', 'Source changed during projection')
            self.opened[workspace_id]=Opened(root,identity,inputs,records,view,alleles)
            return view

    def get(self, workspace_id):
        with self.lock:
            item=self.opened.get(workspace_id)
            if item is None:
                raise ViewerError('WORKSPACE_NOT_OPEN', 'Open and verify the registered workspace again')
            try:
                if item.identity != snapshot(item.root,item.inputs):
                    raise ViewerError('WORKSPACE_CHANGED', 'Verified files changed; reopen and verify before viewing')
                verify_workflow_output(item.root)
                if item.identity != snapshot(item.root,item.inputs):
                    raise ViewerError('WORKSPACE_CHANGED', 'Files changed during verification')
            except (OSError,ValueError):
                self.opened.pop(workspace_id,None)
                raise
            return item

    def download(self, workspace_id, artifact_id):
        item=self.get(workspace_id)
        source=next((s for s in item.view.artifacts if s.artifact_id==artifact_id),None)
        if source is None or not source.downloadable:
            raise ViewerError('UNVERIFIED_ARTIFACT', 'Artifact is not an approved download')
        data=read_bound(item.root,item.records[source.name])
        self.get(workspace_id)
        return source,data
