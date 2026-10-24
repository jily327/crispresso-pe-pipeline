"""Verify the focused production diff and source/wheel byte identity."""
import ast,hashlib,json,subprocess,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[3];base='67734b842d3295a9c40e2981724d981cc060fd80'
changes=subprocess.check_output(['git','diff',base,'--name-only','--','src'],cwd=root,text=True).splitlines()
assert set(changes)=={'src/peanalyzer/routing.py','src/peanalyzer/observability.py','src/peanalyzer/metrics/production.py'}
path='src/peanalyzer/metrics/production.py'
before=subprocess.check_output(['git','show',base+':'+path],cwd=root,text=True);after=(root/path).read_text()
def without_limitations(text):
    tree=ast.parse(text)
    tree.body=[node for node in tree.body if not (isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='LIMITATIONS' for t in node.targets))]
    return ast.dump(tree,include_attributes=False)
assert without_limitations(before)==without_limitations(after)
wheel=Path('/workspace/validation/readthrough/dist-final/crispresso_pe_pipeline-0.7.1-py3-none-any.whl')
identities={}
with zipfile.ZipFile(wheel) as z:
    for p in sorted((root/'src/peanalyzer').rglob('*')):
        if not p.is_file() or p.suffix not in ('.py','.json','.yaml','.csv','.css'):continue
        name=p.relative_to(root/'src').as_posix();data=p.read_bytes();assert z.read(name)==data
        identities[name]=hashlib.sha256(data).hexdigest()
value=dict(base=base,production_files_changed=changes,metrics_production_execution_ast_unchanged=True,only_metrics_limitations_text_changed=True,source_wheel_package_files_identical=True,package_file_sha256=identities,unchanged_layers=['demux','analysis preparation','geometry','backend execution','M4 metric calculations','M5/M5.1','M6/M6.1','M7 orchestration'])
Path(__file__).with_name('scope-and-package.json').write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
print(json.dumps({k:v for k,v in value.items() if k!='package_file_sha256'}))
