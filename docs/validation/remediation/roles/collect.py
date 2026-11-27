"""Check the independent SCI-04 oracle against stored genuine native measurements."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
from zipfile import ZipFile

from peanalyzer.statistics import stats


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report(result, metric):
    group = next(g for g in result['group_summaries']
                 if g['metric_name'] == metric and g['condition']['treatment'] == 'A')
    contrast = next(c for c in result['contrasts'] if c['metric_name'] == metric)
    return dict(expected=group['expected_sample_ids'], n=group['reportable_count'],
                mean=group['mean_biological_sample_fraction'], sd=group['sample_sd_biological_sample_fraction'],
                pooled=group['pooled_read_fraction'], status=contrast['status'], used=contrast['used_group_a_sample_ids'],
                p=contrast['p_value'], q=contrast['q_value'])


def native_recount(root):
    expected = {'bc001': (1, 10), 'bc002': (90, 100), 'bc003': (2, 10), 'bc004': (3, 10)}
    inventory = {}
    for sample, truth in expected.items():
        (archive,) = (root/'metrics'/sample).rglob('Alleles_frequency_table.zip')
        with ZipFile(archive) as z, z.open('Alleles_frequency_table.txt') as raw:
            rows = list(csv.DictReader(io.TextIOWrapper(raw), delimiter='\t'))
        assert len({r['Reference_Name'] for r in rows}) == 1
        aligned = sum(int(r['#Reads']) for r in rows)
        indel = sum(int(r['#Reads']) for r in rows if int(r['n_inserted']) or int(r['n_deleted']))
        assert (indel, aligned) == truth
        inventory[sample] = dict(indel=indel, aligned=aligned, allele_zip_sha256=sha(archive))
    return inventory


def main():
    p = argparse.ArgumentParser()
    p.add_argument('audit_workspace', type=Path, help='Original four-sample control_workflow/workflow')
    p.add_argument('output', type=Path)
    p.add_argument('--package-root', type=Path, required=True, help='Frozen candidate package directory with READY, package.json, env and dist')
    p.add_argument('--corrected-workspace', type=Path)
    args = p.parse_args()
    import peanalyzer
    from peanalyzer.workflow import software_identity
    packaged = json.loads((args.package_root/'package.json').read_bytes())
    tested_commit = (args.package_root/'tested-commit').read_text().strip()
    assert (args.package_root/'READY').exists() and tested_commit == packaged['tested_revision']
    assert Path(peanalyzer.__file__).resolve().is_relative_to((args.package_root/'env').resolve())
    assert software_identity().package_code_sha256 == packaged['package_code_sha256']
    assert sha(args.package_root/'dist'/packaged['wheel']['file']) == packaged['wheel']['sha256']
    root = args.audit_workspace
    inputs = root.parent/'inputs'
    corrected = stats(manifest_path=root/'metrics/manifest.csv', samples_path=inputs/'samples.csv',
                      contrasts_path=inputs/'contrasts.yaml').model_dump()
    bio = report(corrected,'indel_fraction')
    expected = dict(expected=['bio1'],n=1,mean=.1,sd=None,pooled=.1,status='NOT_ASSESSABLE',used=['bio1'],p=None,q=None)
    assert bio == expected
    control = next(o for o in corrected['observations'] if o['sample_id']=='bc002' and o['metric_name']=='indel_fraction')
    assert (control['numerator'],control['denominator'],control['fraction']) == (90,100,.9)
    plan = json.loads((root/'workflow/plan.json').read_bytes())
    result = dict(audited_revision='2f567b88628eeb287bacc9febf3b65b3a00bfc7a',
                  statistics_revision=tested_commit, wheel_sha256=packaged['wheel']['sha256'],
                  installed_package_sha256=packaged['package_code_sha256'], python_version=sys.version.split()[0],
                  input_hashes={f.name:sha(f) for f in sorted(inputs.iterdir()) if f.is_file()},
                  audit_backend=plan['backend_identity'], direct_native_allele_recount=native_recount(root),
                  audit_summary=report(json.loads((root/'statistics/result.json').read_bytes()),'indel_fraction'),
                  corrected_public_stats_over_same_genuine_M4=bio, control_measurement=[90,100,.9])
    if args.corrected_workspace:
        from openpyxl import load_workbook
        from peanalyzer.gui.summary_workbook import FILENAME
        from peanalyzer.gui.workspace import WorkspaceStore
        from peanalyzer.workflow import verify_workflow_output
        fresh = args.corrected_workspace
        verify_workflow_output(fresh)
        actual = json.loads((fresh/'statistics/result.json').read_bytes())
        assert report(actual, 'indel_fraction') == expected
        store = WorkspaceStore([])
        view = store.register_completed('PCR negative control',fresh,finalize=True)
        (qc,) = (o for o in view.observations if o.sample_id=='bc002' and o.metric_name=='indel_fraction')
        assert (qc.numerator,qc.denominator,qc.fraction,qc.biological_eligible)==('90','100',.9,False)
        book = load_workbook(fresh/FILENAME, read_only=True)
        try:
            rows = list(book['Control and technical QC'].values)
            (excel,) = (r for r in rows if r[1]=='bc002' and r[5]=='indel_fraction')
            assert excel[2:4]==('negative_control',False) and excel[9:12]==('90','100',.9)
        finally:
            book.close()
        result['fresh_corrected_workflow'] = dict(verified=True, summary=expected,
            source_workflow_sha256=sha(fresh/'workflow_manifest.json'),native=native_recount(fresh),
            role_qc_tsv_sha256=sha(fresh/'statistics/control_and_technical_qc.tsv'),export_workbook_sha256=sha(fresh/FILENAME),
            viewer_and_excel_control_counts=[90,100,.9],gui_biological_eligible=False)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')


if __name__=='__main__':
    main()
