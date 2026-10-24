"""Replay 72 single-copy panels under a specified router without altering geometry."""
import argparse,importlib.util,json,sys
from pathlib import Path
import peanalyzer.routing as routing
from peanalyzer.geometry import geometry
from peanalyzer.remediation import indel_designs,pair

def load_router(path):
    spec=importlib.util.spec_from_file_location('qualification_router',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module

def grid(module):
    previous=routing.route_pair;routing.route_pair=module.route_pair
    try:
        rows=[]
        for descriptor,targets in indel_designs():
            for target in targets:
                panel=[target];report=geometry(panel);trials=[]
                for state,sequence in [('WT',target.wt_sequence),('PE',target.prime_edited_sequence)]:
                    for length in sorted({100,150,len(sequence)}):
                        result=module.route_pair(pair(sequence,length=length),panel,report,module.RoutingPolicy())
                        trials.append(dict(state=state,length=length,category=result['category'],assigned_copy=result['assigned_copy'],reason=result['reason']))
                rows.append(dict(design=descriptor['id'],copy=target.copy_name,geometry_status=report['status'],geometry_reasons=report['reasons'],trials=trials))
        return rows
    finally:routing.route_pair=previous

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--router',type=Path);a=p.parse_args()
    rows=grid(load_router(a.router) if a.router else routing)
    a.output.write_text(json.dumps(rows,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(panels=len(rows),allowed=sum(r['geometry_status']!='BLOCKED' for r in rows),blocked=sum(r['geometry_status']=='BLOCKED' for r in rows))))
