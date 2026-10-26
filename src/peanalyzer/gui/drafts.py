"""Ephemeral revisioned drafts and explicit local file capabilities; no workspace writes."""
from pathlib import Path
import stat
import threading
import uuid
from peanalyzer.workflow_storage import no_symlinks, sha, digest
from peanalyzer.gui.workspace import ViewerError, safe_registration, snapshot
from peanalyzer.gui.setup_models import SetupFile, DraftContent, DraftView
from peanalyzer.gui.setup_validation import compile_draft


class SetupReferences:
    def __init__(self, files=(), archives=(), output_roots=()):
        self.paths={};self.entries={}
        for kind,paths in [('fastq',files),('demux',archives),('output_root',output_roots)]:
            for path in paths:
                path=safe_registration(path)
                key=uuid.uuid4().hex
                self.paths[key]=path
                # A short suffix distinguishes selections without exposing absolute paths.
                label=path.name
                used=[e.label for e in self.entries.values()]
                if label in used:label=path.parent.name+' / '+label
                if label in used:label+=' ('+str(len(used)+1)+')'
                self.entries[key]=SetupFile(file_id=key,label=label,kind=kind)

    def resolve(self, key, kind):
        if key not in self.paths or self.entries[key].kind!=kind:
            raise ViewerError('INVALID_FILE_REFERENCE','Select a file registered by the local launcher')
        path=no_symlinks(self.paths[key])
        mode=path.stat().st_mode
        if not (stat.S_ISREG(mode) if kind=='fastq' else stat.S_ISDIR(mode)):
            raise ViewerError('INVALID_FILE_REFERENCE','Registered reference has the wrong file type')
        return path

    def label(self,key):
        return self.entries[key].label

    def identity(self,key):
        path=self.resolve(key,self.entries[key].kind)
        if path.is_file():return dict(name=path.name,sha256=sha(path),size_bytes=str(path.stat().st_size))
        return dict(name=path.name,inventory_sha256=digest(snapshot(path)))

    def signature(self,content):
        result={}
        for role in ('r1','r2','demux'):
            key=getattr(content,role)
            if key:
                if key not in self.entries:raise ViewerError('INVALID_FILE_REFERENCE','Unknown input capability')
                result[role]=self.identity(key)
        if content.output_root:
            parent=self.resolve(content.output_root,'output_root')
            result['output_parent_identity']=[parent.stat().st_dev,parent.stat().st_ino]
            from peanalyzer.workflow_storage import owned
            if content.workspace_name:
                result['output_exists']=owned(parent,content.workspace_name).exists()
        return result


class DraftStore:
    def __init__(self,references,protected=()):
        self.references=references;self.protected=tuple(Path(p) for p in protected)
        self.drafts={};self.identities={};self.frozen={};self.lock=threading.RLock()

    def create(self):
        with self.lock:
            view=DraftView(draft_id=uuid.uuid4().hex,revision=0,content=DraftContent())
            self.drafts[view.draft_id]=view
            return view.model_copy(deep=True)

    def get(self,key):
        if key not in self.drafts:raise ViewerError('DRAFT_NOT_FOUND','Draft no longer exists')
        return self.drafts[key].model_copy(deep=True)

    def check(self,key,revision):
        view=self.get(key)
        if revision!=view.revision:raise ViewerError('STALE_DRAFT_REVISION','Reload the current draft before updating or validating')
        return view

    def editable(self,key):
        if key in self.frozen:raise ViewerError('DRAFT_LOCKED','This draft belongs to an accepted job; start a new analysis to edit.')

    def patch(self,key,request):
        with self.lock:
            self.editable(key)
            view=self.check(key,request.revision)
            view.content=request.content.model_copy(deep=True);view.revision+=1;view.validation=None
            self.drafts[key]=view;self.identities.pop(key,None)
            return view.model_copy(deep=True)

    def validate(self,key,revision):
        with self.lock:
            self.editable(key)
            view=self.check(key,revision)
            self.drafts[key].validation=None
            self.identities.pop(key,None)
            try:before=self.references.signature(view.content)
            except (ValueError,OSError):before=None
            result=compile_draft(view.content,revision,self.references,self.protected)
            if result.status=='VALID':
                after=self.references.signature(view.content)
                if before!=after:raise ViewerError('DRAFT_INPUT_CHANGED','Inputs changed during validation; validate again')
                self.identities[key]=after
            else:self.identities.pop(key,None)
            view.validation=result;self.drafts[key]=view
            return result.model_copy(deep=True)

    def preview(self,key,revision):
        with self.lock:
            view=self.check(key,revision)
            if not view.validation or view.validation.status!='VALID':
                raise ViewerError('DRAFT_NOT_VALIDATED','Validate the current draft before Review')
            try:
                if self.references.signature(view.content)!=self.identities[key]:
                    raise ValueError('Input identity changed')
            except (OSError,ValueError,KeyError) as exc:
                self.drafts[key].validation=None;self.identities.pop(key,None)
                raise ViewerError('DRAFT_INPUT_CHANGED','Inputs or destination changed; validate again') from exc
            return view.validation.preview.model_copy(deep=True)

    def delete(self,key,revision):
        with self.lock:
            self.editable(key)
            self.check(key,revision);self.drafts.pop(key);self.identities.pop(key,None)
