"""Record source-bound dimer counts and cross-run physical input identity."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def measurement(root):
    plan=read(root/'workflow/workflow/plan.json')
    result=read(next((root/'workflow/metrics').rglob('result.json')))
    exact=result['target_metrics']['total_precise_pe']
    native=result['target_metrics']['target_crispresso_native_pe']
    copy=result['copies']['copy1']
    info=read(next((root/'workflow/metrics/bc001/T1/comparator').rglob('CRISPResso2_info.json')))
    return dict(package_code_sha256=plan['software_identity']['package_code_sha256'],
        target_exact=[exact['numerator'],exact['denominator']], target_status=exact['status'],
        target_native=[native['numerator'],native['denominator']], raw_input=native['backend_input_reads'],
        backend_aligned=native['aligned_reads'],backend_unaligned=native['unaligned_reads'],
        backend_version=info['running_info']['version'],runtime_digest=result['provenance']['runtime_digest'],
        product_exclusions=exact['products']['exclusion_reason_counts'],
        copy_native=[copy['native']['numerator'],copy['native']['denominator']],
        copy_exact_status=copy['precise']['status'],copy_exact_reasons=copy['precise']['reason_codes'],
        raw_fastq_content_sha256={p.name:sha(gzip.decompress(p.read_bytes())) for p in sorted((root/'input').glob('*.fastq.gz'))})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('original_audit',type=Path)
    p.add_argument('reproduced_old',type=Path)
    p.add_argument('fixed',type=Path)
    p.add_argument('new_result',type=Path)
    args=p.parse_args()
    original=measurement(args.reproduced_old)
    current=measurement(args.fixed)
    assert original['target_exact']==[5,15] and current['target_exact']==[0,10]
    assert original['target_native']==current['target_native']==[0,10]
    audit_fastqs={p.name:sha(gzip.decompress(p.read_bytes())) for p in (args.original_audit/'dimer_run/input').glob('*.fastq.gz')}
    assert original['raw_fastq_content_sha256']==current['raw_fastq_content_sha256']==audit_fastqs
    pre_ref='2f567b88628eeb287bacc9febf3b65b3a00bfc7a'
    fixed_ref=read(args.fixed/'workflow/workflow/plan.json')['software_identity']['git_commit']
    evidence=dict(audited_revision=pre_ref, corrected_revision=fixed_ref, independent_expected=[0,10],
        original_reproduction_script_sha256=sha((args.original_audit/'dimer.py').read_bytes()),
        original_audit_result_sha256=sha((args.original_audit/'results/dimer.json').read_bytes()),
        fixed_input_matches_original=True,before=original,after=current,
        family_excluded=read(args.fixed/'comparison.json')['family_excluded'])
    with args.new_result.open('x') as out:
        json.dump(evidence,out,indent=2,sort_keys=True)
        out.write('\n')


if __name__=='__main__':
    main()
