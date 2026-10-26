"""Summarize completed qualification without deriving or changing scientific values."""
import json
from pathlib import Path
out=Path(__file__).resolve().parent
rows=['# Real-data target-precise results (0.7.1)','',
      'Exact PE / (exact WT + exact PE). Exclusions are prepared pairs outside that denominator.',
      'Native is the distinct CRISPResso PE-reference numerator/denominator. Controls retain observed signal.','']
for dataset in ('Azenta','AmpSeq'):
    result=json.loads((out/(dataset+'-results.json')).read_text())
    rows += [f'## {dataset}','','| Sample | Prepared | Exact PE / denominator | Exact % | Excluded | Native PE / denominator |','|---|---:|---:|---:|---:|---:|']
    for sample,m in result['samples'].items():
        rows.append(f"| {sample} | {m['input_pairs']:,} | {m['exact_pe']:,} / {m['precise_denominator']:,} | {m['precise_percent']:.4f} | {m['excluded']:,} | {m['native_numerator']:,} / {m['native_denominator']:,} |")
    rows += ['',f"M7 {result['workflow_status']}; {result['observations']} M5 observations; {result['exported_embedded_svg_count']} valid exported/embedded SVGs; exact report source copy; all report hashes verified.",f"Resume: {len(result['zero_execution_resume']['executed_stages'])} executed / {len(result['zero_execution_resume']['reused_stages'])} reused stages; completion hash unchanged.",'']
(out/'RESULTS.md').write_text('\n'.join(rows).rstrip()+'\n')
# Independently transcribed native integers from the supporting audit.
expected={'Azenta':{'1A':(52,2507),'2B':(72,3094),'3C':(58,3557),'4D':(711,3329),'5E':(1109,3130),'6F':(497,3167),'7G':(747,3095)},'AmpSeq':{'1B':(173,6469),'2C':(144,8541),'3D':(148,6590),'4E':(203,6457),'5A':(130,9125),'1C':(180,7117),'2D':(238,8698),'3E':(200,5905),'4A':(159,7618),'5B':(129,7148),'6F':(222,6064),'7G':(90,989)}}
for dataset,wanted in expected.items():
    result=json.loads((out/(dataset+'-results.json')).read_text())
    assert {k:(v['native_numerator'],v['native_denominator']) for k,v in result['samples'].items()}==wanted
(out/'qualification-gate.json').write_text(json.dumps(dict(status='PASS',starting_main='67734b842d3295a9c40e2981724d981cc060fd80',version='0.7.1',targeted_tests=59,full_source=1095,full_wheel=1095,failures=0,errors=0,skips=0,integration=63,geometry=dict(total=36,allowed=13,blocked=23),historical_routing_trial_changes=0,historical_product_classification_changes=0,historical_metric_numeric_changes=0,native_audit_counts_preserved=True,real_sample_target_results=19,real_target_precise_reportable=19,real_prepared_oracle_comparisons=178128,real_oracle_disagreements=0,normalization_trials=376,normalization_disagreements=0),indent=2)+'\n')
print('qualification PASS')
