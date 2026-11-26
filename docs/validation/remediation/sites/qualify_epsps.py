"""Rebuild physical EPSPS populations, run conventional two-WT Core, replay it with direct Docker."""
import argparse
from collections import Counter
from contextlib import ExitStack
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from peanalyzer.backend.intended_sites import run_core_sites
from peanalyzer.backend.native_runs import write_native_runs, verify_native_runs
from peanalyzer.backend.pooled import resolve_executable
from peanalyzer.docker_runtime import IMAGE
from peanalyzer.fastq import paired_fastq, read_id
from peanalyzer.workflow import software_identity

sys.path.insert(0,str(Path(__file__).resolve().parents[2] / 'epsps-real'))
from audit import calls, rc, sha, validate_sources


@dataclass(frozen=True)
class ConventionalTarget:
    copy_name: str
    wt_sequence: str
    prime_edited_sequence: str

    def model_dump(self, *, mode):
        return asdict(self)  # No experimental guides are supplied for this conventional run.


def write_record(stream, ident, mate, dna, qual):
    stream.write(b'@'+ident+b'/'+str(mate).encode()+b'\n'+dna+b'\n+\n'+qual+b'\n')


def prepare(work, inputs, targets):
    fwd, rev = calls()
    seen = set()
    barcode = Counter()
    with ExitStack() as stack:
        writers = {k:[stack.enter_context((work/f'{k}.R{mate}.fq').open('xb')) for mate in (1,2)]
                   for k in ('1A_acquired','all_acquired','1A_forward','all_forward','SCI02')}
        for one,two in paired_fastq(inputs['EPSPS_1106_R1.fastq.gz'],inputs['EPSPS_1106_R2.fastq.gz']):
            ident=read_id(one,1)
            if ident in seen:
                raise ValueError('Duplicate physical pair')
            seen.add(ident)
            label=fwd.get(one.sequence[:9].decode(),'?') + rev.get(two.sequence[:9].decode(),'?')
            barcode[label]+=1
            if '?' in label:
                continue
            left,right=one.trimmed(26),two.trimmed(27)
            for order, pair in [('acquired',(left,right)),('forward',(right,left))]:
                for name in (['all_'+order, '1A_'+order] if label=='1A' else ['all_'+order]):
                    for m,rec in enumerate(pair,1):
                        write_record(writers[name][m-1],ident,m,rec.sequence,rec.quality_line.rstrip())
        wt,pe=targets[0].wt_sequence,targets[0].prime_edited_sequence
        assert wt[145:147]=='GG' and pe[146]=='A'
        for j,molecule in enumerate([wt]*10 + [pe[:145]+pe[146:]]*5):
            for m,dna in enumerate((molecule[:180],rc(molecule[-180:])),1):
                write_record(writers['SCI02'][m-1],f'gap{j}'.encode(),m,dna.encode(),b'I'*len(dna))
    n=sum(v for k,v in barcode.items() if '?' not in k)
    return {'SCI02':15,'1A_acquired':barcode['1A'],'1A_forward':barcode['1A'],'all_acquired':n,'all_forward':n}, barcode


def run_one(work, key, n, targets, executable):
    cell=work/key
    cell.mkdir(exist_ok=True)
    mates=[work/f'{key}.R{i}.fq' for i in (1,2)]
    sample=dict(pairs=n, files={f'r{i}':{'sha256':sha(p)} for i,p in enumerate(mates,1)})
    if not (cell/'core_sites').exists():
        run_core_sites(targets=targets,r1=mates[0],r2=mates[1],input_pairs=n,core=executable,
                       runtime_digest=IMAGE,output=cell/'core_sites',
                       windows={t.copy_name:'146-146_157-157' for t in targets})
    report=json.loads((cell/'core_sites/aligned_site_counts.json').read_text())
    if (cell/'native_runs.json').exists():
        verify_native_runs(cell,key,'EPSPS',targets,sample)
    else:
        write_native_runs(cell,key,'EPSPS',targets,sample)
    native=json.loads((cell/'native_runs.json').read_text())['runs']
    item,=native
    assert item['runtime_identity_status']=='VERIFIED' and item['extraction_status']=='PASS',item['reasons']
    assert 'report' in item['paths'] and item['recount_status']=='PASS'
    direct=work/(key+'-manual')
    if not (direct/'parity.json').exists():
        subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'direct_parity.py'),
                        str(cell),item['id'],str(direct)],check=True)
    parity=json.loads((direct/'parity.json').read_text())
    assert parity['status']=='PASS'
    return dict(derived=report['combined'], integer_parity=parity, native=item['per_reference'],
                version=report['version'],info_sha256=item['sha256']['info'],argc=len(item['argv']),
                script=(cell/item['paths']['script']).read_text(),source=software_identity().model_dump())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs',type=Path,help='Directory containing exactly one of each original input')
    parser.add_argument('work',type=Path)
    parser.add_argument('--core',default='peanalyzer-crispresso')
    args=parser.parse_args()
    sources,panels=validate_sources(args.inputs)
    targets=[ConventionalTarget(k,v['wt_sequence'],v['intended_pe_sequence']) for k,v in panels['EPSPS_284bp'].items()]
    args.work.mkdir(parents=True,exist_ok=True)
    ledger=args.work/'prepared.json'
    if not ledger.exists():
        counts,barcode=prepare(args.work,sources,targets)
        ledger.write_text(json.dumps(dict(counts=counts,physical_barcodes=barcode,
            input_hashes={k:sha(v) for k,v in sources.items()},prepared_hashes={p.name:sha(p) for p in args.work.glob('*.fq')}),indent=2))
    prepared=json.loads(ledger.read_text())
    for filename,digest in prepared['prepared_hashes'].items():
        assert sha(args.work/filename)==digest
    core=resolve_executable(args.core)
    for population,n in prepared['counts'].items():
        row=run_one(args.work,population,n,targets,core)
        (args.work/(population+'.evidence.json')).write_text(json.dumps(row,indent=2,sort_keys=True)+'\n')
        print(population,row['derived']['double_edit'],flush=True)


if __name__=='__main__':
    main()
