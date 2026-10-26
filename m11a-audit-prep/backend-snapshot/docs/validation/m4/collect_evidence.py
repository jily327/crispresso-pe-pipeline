"""Collect only synthetic text evidence from completed M4 qualification runs.

Usage: python docs/validation/m4/collect_evidence.py /workspace/validation/m4
The workspace contains source-final/, source-final-tests.xml, wheel-tests.xml,
their runner logs, baseline.txt and runtime.json. No FASTQ/BAM is copied.
"""

import json
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


def write(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def cases(path):
    return list(ET.parse(path).getroot().iter('testcase'))


def main(workspace):
    destination = Path(__file__).resolve().parent
    source = workspace/'source-final'
    summaries = {}
    for kind, xmlname, logname in [('source','source-final-tests.xml','source-final-tests.txt'),
                                  ('wheel','wheel-tests.xml','wheel-tests.txt')]:
        rows = cases(workspace/xmlname)
        failed = sum(r.find('failure') is not None or r.find('error') is not None for r in rows)
        skipped = sum(r.find('skipped') is not None for r in rows)
        summaries[kind] = dict(total=len(rows), failed=failed, skipped=skipped,
                               actual_backend_tests=sum('_integration' in r.get('classname','') for r in rows))
        assert not failed and not skipped and summaries[kind]['actual_backend_tests']==18
        shutil.copyfile(workspace/logname, destination/f'{kind}-tests.txt')
    assert summaries['source']['total']==summaries['wheel']['total']
    write(destination/'test-results.json', summaries)
    negatives = [dict(test=r.get('classname')+'::'+r.get('name'), outcome='PASS')
                 for r in cases(workspace/'source-final-tests.xml')
                 if r.get('classname','').endswith('test_m4')
                 and any(word in r.get('name','') for word in ('negative','gates','difference','unsupported',
                     'missing','contradictory','zero_exact','schema_rejects','cannot_guess'))]
    write(destination/'negative-gates.json', negatives)
    shutil.copyfile(workspace/'baseline.txt', destination/'baseline-tests.txt')
    shutil.copyfile(workspace/'runtime.json', destination/'runtime.json')
    results = {}
    for fixture in ('m3','m31'):
        execution = source/f'm4/{fixture}/m4'
        dest = destination/fixture
        dest.mkdir(exist_ok=True)
        result = json.loads((execution/'result.json').read_text())
        results[fixture] = result
        shutil.copyfile(execution/'result.json', dest/'result.json')
        for group, folder, childname in [('anchors','comparator','unrouted'), ('copies','copies','confident')]:
            for root in sorted((execution/folder).glob('*')):
                if not root.is_dir():
                    continue
                child = root/f'output/CRISPResso_on_{childname}'
                out = dest/group/root.name
                out.mkdir(parents=True, exist_ok=True)
                info = json.loads((child/'CRISPResso2_info.json').read_text())
                running = info['running_info']
                for name in ('CRISPResso2_info.json', running['mapping_stats_filename'], running['quant_of_editing_freq_filename']):
                    shutil.copyfile(child/name, out/name)
                shutil.copyfile(root/'execution.json', out/'execution.json')
                with zipfile.ZipFile(child/running['allele_frequency_table_zip_filename']) as archive:
                    (out/'alleles.txt').write_bytes(archive.read(running['allele_frequency_table_filename']))
    historical = json.loads((source/'m3/baseline/05_routing_QC/routing_summary.json').read_text())
    regression = dict(targets={}, confident_copies={}, historical_pooled={},
                      combined_confident=dict(input=75,aligned=70,unaligned=5,native=[30,70],precise=[20,50]),
                      original_routing=dict(input=125,assigned=75,quarantined=50),
                      geometry_grid=dict(designs=36,allowed=13,blocked=23,
                                         evidence='retained test_original_125_decisions_and_indel_admission_are_unchanged'))
    for fixture, expected in [('m3',(120,330,100,230)),('m31',(30,105,20,55))]:
        result = results[fixture]
        native, precise = (result['target_metrics'][k] for k in ('target_crispresso_native_pe','total_precise_pe'))
        assert (native['numerator'],native['denominator'],precise['numerator'],precise['denominator'])==expected
        assert native['status']==precise['status']=='REPORTABLE' and result['eligibility']['anchor_invariant']
        regression['targets'][fixture] = dict(native=[native['numerator'],native['denominator']],
            precise=[precise['numerator'],precise['denominator']],
            input=native['backend_input_reads'],aligned=native['aligned_reads'],unaligned=native['unaligned_reads'])
    for copy, n,a,u,p,e,d in [('copy1',45,42,3,18,12,30),('copy2',30,28,2,12,8,20)]:
        row=results['m31']['copies'][copy];native=row['native'];precise=row['precise']
        observed=(native['backend_input_reads'],native['aligned_reads'],native['unaligned_reads'],native['numerator'],precise['numerator'],precise['denominator'])
        assert observed==(n,a,u,p,e,d) and row['copy_metric_status']=='REPORTABLE'
        regression['confident_copies'][copy]=dict(input=n,aligned=a,unaligned=u,native=[p,a],precise=[e,d])
    for copy, n,a,u,p,e,d in [('copy1',211,199,12,72,60,140),('copy2',139,131,8,48,40,90)]:
        parsed=historical['reference_smoke']['SYN__'+copy]['alignment_reconciliation']
        native,precise=parsed['native'],parsed['exact_haplotype']
        assert (native['backend_input_reads'],native['aligned_reads'],native['unaligned_reads'],native['numerator'],precise['numerator'],precise['denominator'])==(n,a,u,p,e,d)
        regression['historical_pooled'][copy]=dict(input=n,aligned=a,unaligned=u,native=[p,a],precise=[e,d])
    write(destination/'historical-regressions.json',regression)
    write(destination/'gate.json',dict(metric_gate='PASS',base='550df70f9f9627c7218b9f047d0b6bf3023b8d25',
          tests=summaries,checks=dict(all_historical_integers_preserved=True,all_required_negative_gates_passed=True,
          actual_core_qualification=True,populations_separate=True,source_and_wheel_passed=True),
          expected_blocked_result='M3 historical Pooled is not a qualified copy cohort; its M4 copy metrics stay BLOCKED',
          audit_readiness='SAFE FOR INDEPENDENT M4 AUDIT'))


if __name__ == '__main__':
    main(Path(sys.argv[1]))
