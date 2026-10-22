"""Direct Core handoff accepts independently verified routing cohorts only."""

import json
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from peanalyzer.analysis_verify import verify_analysis_output
from peanalyzer.backend.metrics import parse_child, backend_failure_code
from peanalyzer.backend.pooled import BackendError, Executable, FIELDS, preflight_guides, utc_now
from peanalyzer.demux_verify import read_json, sha256_file
from peanalyzer.fastq import paired_fastq, read_id
from peanalyzer.geometry import geometry
from peanalyzer.provenance import software_provenance
from peanalyzer.schemas import Target
from peanalyzer.routing import RoutingPolicy, decide, enforce_edit_flanking, policy_identity


def verify_routing_output(root: Path) -> dict:
    root=Path(root)
    if root.is_symlink() or any('.incomplete-' in p for p in root.resolve().parts): raise ValueError('unpublished routing path')
    data=read_json(root/'routing_manifest.json')
    if data['schema_version']!=1 or data['status']!='completed': raise ValueError('incomplete routing')
    verified=verify_analysis_output(Path(data['analysis_root']))
    if verified.manifest_sha256!=data['analysis_manifest_sha256']: raise ValueError('analysis identity mismatch')
    targets=[Target.model_validate(t) for t in data['targets']]
    policy=RoutingPolicy(**data['policy'])
    if data.get('policy_identity')!=policy_identity(policy): raise ValueError('routing policy identity mismatch')
    if geometry(targets,min_distinguishing_sites=policy.min_distinguishing_sites)['status']=='BLOCKED': raise ValueError('blocked target geometry')
    if set(data['cohorts'])!={*(t.copy_name for t in targets),'quarantine'}: raise ValueError('cohort inventory mismatch')
    ledger=root/'routing_ledger.jsonl'
    if ledger.is_symlink() or sha256_file(ledger)!=data['ledger_sha256']: raise ValueError('ledger changed')
    rows=[json.loads(line) for line in ledger.read_text().splitlines()]
    copies=sorted(t.copy_name for t in targets)
    categories=Counter(); cohort_counts=Counter()
    for row in rows:
        category,assigned=row['category'],row['assigned_copy']
        compatible=row.get('compatible_copies')
        if not isinstance(compatible,list): raise ValueError('missing compatible-copy semantics')
        if category=='ASSIGNED_COPY':
            if assigned not in copies or compatible!=[assigned]: raise ValueError('assigned ledger semantics mismatch')
        elif assigned is not None:
            raise ValueError('quarantine ledger cannot assign a copy')
        if len(compatible)!=len(set(compatible)) or not set(compatible)<=set(copies):
            raise ValueError('invalid compatible copies')
        if category!='ALIGNMENT_FAILURE' and len(copies)>1:
            if not isinstance(row.get('edit_flanking'),list): raise ValueError('missing observed edit-flanking evidence')
            decision=enforce_edit_flanking(decide(row['evidence'],copies,policy),row['edit_flanking'])
            if decision!=(category,assigned,compatible):
                raise ValueError('ledger decision semantics mismatch')
        elif category not in ('ALIGNMENT_FAILURE','ASSIGNED_COPY'):
            raise ValueError('unknown ledger category')
        categories[category]+=1
        cohort_counts[assigned or 'quarantine']+=1
    if dict(categories)!=data['categories']: raise ValueError('ledger category counts mismatch')
    if any(cohort_counts[c]!=info['pairs'] for c,info in data['cohorts'].items()):
        raise ValueError('ledger cohort counts mismatch')
    expected={r['read_id']:r['assigned_copy'] or 'quarantine' for r in rows}
    if len(expected)!=len(rows): raise ValueError('duplicate ledger ID')
    actual={}; contents={}
    for cohort,info in data['cohorts'].items():
        paths=[]
        for mate in (1,2):
            entry=info['files'][f'r{mate}']; path=root/f'{cohort}_R{mate}.fastq.gz'
            if entry['path']!=path.name or path.is_symlink() or path.stat().st_size!=entry['size_bytes'] or sha256_file(path)!=entry['sha256']:
                raise ValueError('routing FASTQ integrity failure')
            paths.append(path)
        count=0
        for pair in paired_fastq(*paths):
            identifier=read_id(pair[0],1).decode()
            if identifier in actual: raise ValueError('duplicate output pair')
            actual[identifier]=cohort; contents[identifier]=tuple(r.to_bytes() for r in pair); count+=1
        if count!=info['pairs']: raise ValueError('routing count mismatch')
    if actual!=expected or len(actual)!=data['input_pairs']: raise ValueError('routing partition mismatch')
    sample=verified.manifest['samples'][data['sample_id']]
    paths=[verified.root/sample['files'][f'r{m}']['path'] for m in (1,2)]
    for pair in paired_fastq(*paths):
        if contents.pop(read_id(pair[0],1).decode(),None)!=tuple(r.to_bytes() for r in pair): raise ValueError('routing did not preserve original pair')
    if contents: raise ValueError('unexpected output IDs')
    return data


def run_confident_core(routing_root: Path, copy_name: str, output: Path, core: Executable, *, runtime_identity: dict | None=None) -> dict:
    data=verify_routing_output(routing_root)
    if not data['policy_identity']['qualified']:
        raise ValueError('production Core requires qualified routing policy')
    targets=[Target.model_validate(t) for t in data['targets']]
    target=next((t for t in targets if t.copy_name==copy_name),None)
    if target is None: raise ValueError('unknown biological copy (quarantine is not a copy)')
    preflight_guides([target])
    cohort=data['cohorts'][copy_name]
    if not cohort['pairs']: raise ValueError('empty confident cohort; no backend metric')
    if core.version!='2.3.4': raise BackendError('VERSION_MISMATCH','requires 2.3.4')
    output=Path(output).absolute()
    if output.exists() or output.is_symlink(): raise ValueError('output exists')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='peanalyzer-core-',dir='/tmp') as temporary:
        work=Path(temporary)
        for mate in (1,2):
            source=Path(routing_root)/cohort['files'][f'r{mate}']['path']
            shutil.copyfile(source,work/f'input_R{mate}.fastq.gz')
            if sha256_file(work/f'input_R{mate}.fastq.gz')!=cohort['files'][f'r{mate}']['sha256']: raise ValueError('input changed during copy')
        argv=[core.path,'-r1','input_R1.fastq.gz','-r2','input_R2.fastq.gz','--amplicon_seq',target.wt_sequence,
              '--name','confident','--output_folder','output','--write_detailed_allele_table','--keep_intermediate','--suppress_report','--suppress_plots']
        for column,field in list(FIELDS.items())[2:]:
            value=getattr(target,field)
            if value is not None: argv.extend(['--'+column,str(value)])
        manifest=dict(schema_version=1,status='running',software=software_provenance(),runtime_identity=runtime_identity,
                      executable_path=core.path,version_probe=core.probe,argv=argv,cwd=str(work),output_path=str(output),
                      routing_manifest_sha256=sha256_file(Path(routing_root)/'routing_manifest.json'),
                      inputs=cohort,started_at=utc_now(),return_code=None)
        error=None
        try:
            with (work/'stdout.txt').open('w') as out,(work/'stderr.txt').open('w') as err:
                try:
                    result=subprocess.run(argv,cwd=work,stdout=out,stderr=err,check=False)
                except OSError as exc:
                    raise BackendError('COMMAND_FAILED', str(exc)) from exc
            manifest['return_code']=result.returncode
            if result.returncode: raise BackendError('COMMAND_FAILED',f'Core exit {result.returncode}')
            metrics=parse_child(work/'output/CRISPResso_on_confident',routed_pairs=cohort['pairs'],one_input_record_per_pair=True)
            (work/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
            manifest['status']='completed'
        except (OSError,ValueError,BackendError) as exc:
            error=exc; manifest.update(status='failed',error=str(exc),reason_code=backend_failure_code(exc))
        finally:
            manifest['ended_at']=utc_now()
            (work/'execution.json').write_text(json.dumps(manifest,indent=2)+'\n')
            stage=Path(tempfile.mkdtemp(prefix=f'.{output.name}.incomplete-',dir=output.parent))
            try:
                shutil.copytree(work,stage,dirs_exist_ok=True)
                if output.exists(): raise ValueError('output appeared during execution')
                stage.rename(output)
            finally:
                if stage.exists(): shutil.rmtree(stage)
        if error: raise error
        return metrics
