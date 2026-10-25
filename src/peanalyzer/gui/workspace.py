"""In-memory registrations and immutable verified snapshots, outside scientific workspaces."""
from dataclasses import dataclass
from copy import deepcopy
from types import MappingProxyType
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


def snapshot(root, inputs=(), external_roots=()):
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
    # Analyze-mode source archives are immutable inputs too. Remember their
    # inventory, not only the already-known files, so new unexpected FASTQs
    # cannot bypass the original demux verifier's exact-inventory contract.
    for path in external_roots:
        for key,value in snapshot(Path(path)).items():
            result['external:'+str(path)+':'+key]=value
    return result


def registration_labels(registrations):
    """Disambiguate only default labels, using the shortest unique path suffix."""
    rows=[(label,safe_registration(path)) for label,path in registrations]
    labels=[label if label is not None else path.name for label,path in rows]
    defaults=[i for i,(label,_) in enumerate(rows) if label is None]
    depths={i:1 for i in defaults}
    while True:
        collisions={label for label in labels if labels.count(label)>1}
        changed=False
        for i in defaults:
            if labels[i] not in collisions:
                continue
            parts=rows[i][1].parts[1:]  # Never expose the absolute root prefix.
            if depths[i]<len(parts):
                depths[i]+=1
                labels[i]=' / '.join(parts[-depths[i]:])
                changed=True
        if not changed:
            break
    # Repeated registration of the same path, or collision with an explicit label.
    used={labels[i] for i in range(len(rows)) if i not in defaults}
    for i in defaults:
        label=labels[i]; suffix=2
        while labels[i] in used:
            labels[i]=f'{label} ({suffix})';suffix+=1
        used.add(labels[i])
    return [(labels[i],path) for i,(_,path) in enumerate(rows)]


@dataclass(frozen=True)
class Opened:
    root: Path
    identity: dict
    inputs: tuple[str, ...]
    external_roots: tuple[str, ...]
    records: dict
    view: object
    alleles: dict


class WorkspaceStore:
    def __init__(self, registrations):
        self.registrations={uuid.uuid4().hex:(label,path) for label,path in registration_labels(registrations)}
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
            # Read the plan only to capture source identities BEFORE verification.
            # The authoritative verifier below validates that plan and its lineage.
            plan=Plan.model_validate(read_json(owned(root,'workflow/plan.json')))
            inputs=tuple(a.source_path for a in plan.inputs.values())
            external_roots=(plan.normalized_options['external_demux'],) if plan.mode=='analyze' else ()
            identity=snapshot(root,inputs,external_roots)
            if initial != {k:v for k,v in identity.items() if not k.startswith(('input:','external:'))}:
                raise ViewerError('WORKSPACE_CHANGED', 'Workspace changed during verification')
            manifest=verify_workflow_output(root)
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
            if identity != snapshot(root,inputs,external_roots):
                raise ViewerError('WORKSPACE_CHANGED', 'Source changed during projection')
            self.opened[workspace_id]=Opened(root,MappingProxyType(identity),inputs,external_roots,
                MappingProxyType(records),view.model_copy(deep=True),alleles)
            return view

    def get(self, workspace_id):
        with self.lock:
            item=self.opened.get(workspace_id)
            if item is None:
                raise ViewerError('WORKSPACE_NOT_OPEN', 'Open and verify the registered workspace again')
            try:
                if item.identity != snapshot(item.root,item.inputs,item.external_roots):
                    raise ViewerError('WORKSPACE_CHANGED', 'Verified files changed; reopen and verify before viewing')
            except (OSError,ValueError):
                self.opened.pop(workspace_id,None)
                raise
            # Callers cannot mutate the cached typed projection through a response.
            return Opened(item.root,item.identity,item.inputs,item.external_roots,item.records,
                item.view.model_copy(deep=True),deepcopy(item.alleles))

    def download(self, workspace_id, artifact_id):
        with self.lock:
            item=self.get(workspace_id)
            source=next((s for s in item.view.artifacts if s.artifact_id==artifact_id),None)
            if source is None or not source.downloadable:
                raise ViewerError('UNVERIFIED_ARTIFACT', 'Artifact is not an approved download')
            try:
                data=read_bound(item.root,item.records[source.name])
                self.get(workspace_id)
            except (OSError,ValueError):
                self.opened.pop(workspace_id,None)
                raise
            return source,data
