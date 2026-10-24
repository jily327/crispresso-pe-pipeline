"""Additional reference-prefix tail probe, independent of vendor motifs."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tests'))
from test_readthrough import targets,records
from peanalyzer.observability import assess_pair
from peanalyzer.routing import route_pair,RoutingPolicy
from peanalyzer.geometry import geometry
rows=[];ts=targets();report=geometry(ts)
for t in ts:
    for state in ('wt_sequence','prime_edited_sequence'):
        seq=getattr(t,state)
        for n in (5,27,70):
            pair=records(seq,len(seq)+n,len(seq)+n,seq[:n])
            assessed=assess_pair(pair,ts);routed=route_pair(pair,ts,report,RoutingPolicy())
            assert assessed['canonical']==('exact_WT' if state=='wt_sequence' else 'exact_PE')
            assert routed['assigned_copy']==t.copy_name
            rows.append(dict(copy=t.copy_name,state=state,partial_reference_tail_length=n,exact=assessed['canonical'],routing=routed['assigned_copy']))
Path(__file__).with_name('partial-reference-tail-probes.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(dict(probes=len(rows),passed=True)))
