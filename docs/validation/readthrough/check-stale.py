"""Create a disposable 0.7.0 workspace, then test normal 0.7.1 invalidation."""
import argparse,json,sys
from pathlib import Path
from peanalyzer import __version__
import peanalyzer.workflow as w
p=argparse.ArgumentParser();p.add_argument('mode',choices=['baseline','stale','rebuild']);p.add_argument('root',type=Path);a=p.parse_args()
if a.mode=='baseline':
    assert __version__=='0.7.0'
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tests'))
    from m7_fixtures import fixture
    options=fixture(a.root/'inputs',samples=2,copies=2,reads=4)
    options['output']=a.root/'workspace';options['crispresso']='/workspace/validation/m61/bin/CRISPResso'
    (a.root/'options.json').write_text(json.dumps({k:str(v) if isinstance(v,Path) else v for k,v in options.items()},indent=2)+'\n')
    result=w.execute_workflow(**options)
else:
    assert __version__=='0.7.1'
    options=json.loads((a.root/'options.json').read_text())
    if a.mode=='stale':
        def forbidden(*args,**kwargs):raise AssertionError('stale resume executed science')
        for name in ('demultiplex','prepare_analysis_fastqs','route_analysis','run_metrics','summarize','stats','generate_report'):setattr(w,name,forbidden)
        try:w.execute_workflow(**options,resume=True)
        except w.WorkflowError as e:
            assert e.code=='STALE_STAGE_IDENTITY',str(e)
            result=dict(version=__version__,rejected=True,error_code=e.code,message=str(e),executors_called=0)
        else:raise AssertionError('old software silently reused')
    else:result=w.execute_workflow(**options,resume=True,force=['all'])
(a.root/(a.mode+'-result.json')).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps(result))
