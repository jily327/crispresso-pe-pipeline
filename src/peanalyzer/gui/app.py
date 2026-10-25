"""Loopback-only authenticated presentation API and bundled static viewer."""
import secrets
from pathlib import Path
from urllib.parse import urlsplit, quote

from fastapi import FastAPI, Request, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from peanalyzer import __version__
from peanalyzer.workflow import software_identity
from peanalyzer.gui.projection import fields
from peanalyzer.workflow_storage import WorkflowError
from peanalyzer.gui.workspace import WorkspaceStore, ViewerError
from peanalyzer.gui.models import (Capabilities, Registration, OpenRequest, WorkspaceView,
    ObservationPage, AllelePage, ErrorEnvelope, ErrorDetail)

BASE = '9e9a51fb20e56a3421fdfa156375170cd6b257dc'


def create_app(registrations=(), token=None):
    token=token or secrets.token_urlsafe(32)
    store=WorkspaceStore(registrations)
    app=FastAPI(title='PEAnalyzer verified result viewer',docs_url=None,redoc_url=None,openapi_url=None)
    app.state.store=store
    app.state.token=token

    def error(code,detail,stage_id=None,status=409):
        messages={
            'UNAUTHORIZED':'Open the local launcher URL to authorize this viewer.',
            'UNSAFE_ORIGIN':'This request did not come from the local viewer.',
            'WORKSPACE_CHANGED':'The workspace changed. Results have been hidden; reopen to verify.',
            'STALE_STAGE_IDENTITY':'The workspace has a stale scientific identity. Backend-managed recalculation is required.',
            'INCOMPLETE_WORKSPACE':'This folder is not a completed PEAnalyzer workspace.',
            'WORKSPACE_NOT_FOUND':'The registered workspace could not be found.',
            'UNVERIFIED_ARTIFACT':'This artifact is not available through the verified inventory.',
        }
        return JSONResponse(ErrorEnvelope(error=ErrorDetail(code=code,message=messages.get(code,'Workspace verification failed. Scientific results are unavailable.'),
            detail=detail,stage_id=stage_id)).model_dump(),status_code=status)

    @app.middleware('http')
    async def local_boundary(request,call_next):
        host=request.headers.get('host','')
        hostname=urlsplit('http://'+host).hostname
        origin=request.headers.get('origin')
        if hostname not in ('127.0.0.1','localhost','::1') or (origin and origin != 'http://'+host):
            return error('UNSAFE_ORIGIN','Only same-origin loopback requests are allowed',status=403)
        if request.url.path.startswith('/api/') and not secrets.compare_digest(request.headers.get('x-viewer-token',''),token):
            return error('UNAUTHORIZED','Missing or invalid local session token',status=401)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        return response

    @app.exception_handler(WorkflowError)
    async def workflow_error(request,exc):
        return error(exc.code,str(exc),exc.stage_id)

    @app.exception_handler(RequestValidationError)
    async def request_error(request,exc):
        return error('INVALID_REQUEST','Request does not match the viewer contract',status=422)

    @app.exception_handler(ValueError)
    @app.exception_handler(OSError)
    async def invalid(request,exc):
        return error('VERIFICATION_FAILED',str(exc))

    @app.get('/api/v1/capabilities',response_model=Capabilities)
    def capabilities():
        return Capabilities(package_version=__version__,backend_base=BASE,viewer_software=fields(software_identity().model_dump()),
            result_contracts=['m7-v1','m4-v1','m5-v1','m6-v1','indel-nuclease-v1','indel-nuclease-stats-v1','indel-nuclease-report-v1'],
            analysis_modes=['precise_edit','indel_nuclease'],screens=['Overview','Samples','QC','Statistics','Provenance'])

    @app.get('/api/v1/workspaces',response_model=list[Registration])
    def catalog():
        return store.catalog()

    @app.post('/api/v1/workspaces/open',response_model=WorkspaceView)
    def open_workspace(body:OpenRequest):
        return store.open(body.registration_id)

    @app.get('/api/v1/workspaces/{workspace_id}',response_model=WorkspaceView)
    def view(workspace_id:str):
        return store.get(workspace_id).view

    @app.get('/api/v1/workspaces/{workspace_id}/observations',response_model=ObservationPage)
    def observations(workspace_id:str,offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200),
                     sample_id:str|None=None,series_id:str|None=None):
        rows=store.get(workspace_id).view.observations
        rows=[r for r in rows if (sample_id is None or r.sample_id==sample_id) and (series_id is None or r.series_id==series_id)]
        return ObservationPage(items=rows[offset:offset+limit],offset=offset,limit=limit,total=str(len(rows)))

    @app.get('/api/v1/workspaces/{workspace_id}/alleles/{sample_id}',response_model=AllelePage)
    def alleles(workspace_id:str,sample_id:str,offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100)):
        item=store.get(workspace_id)
        if sample_id not in item.alleles:
            raise ViewerError('UNSUPPORTED_DETAIL','Typed alleles are available for nuclease samples only')
        rows,source=item.alleles[sample_id]
        return AllelePage(items=rows[offset:offset+limit],offset=offset,limit=limit,total=str(len(rows)),source=source)

    @app.get('/api/v1/workspaces/{workspace_id}/artifacts/{artifact_id}')
    def download(workspace_id:str,artifact_id:str):
        source,data=store.download(workspace_id,artifact_id)
        return Response(data,media_type='application/octet-stream',headers={
            'Content-Disposition':"attachment; filename*=UTF-8''"+quote(Path(source.name).name,safe=''),
            'X-Artifact-SHA256':source.sha256,'Content-Security-Policy':"sandbox; default-src 'none'"})

    static=Path(__file__).parent/'static'
    if static.is_dir():
        app.mount('/',StaticFiles(directory=static,html=True),name='viewer')
    return app
