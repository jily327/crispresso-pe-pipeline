"""Deterministic sample-level catalog of original, interpreted and independent measurements."""
import csv
import hashlib
import html
import io
import json
from pathlib import Path

from peanalyzer.gui.models import Source
from peanalyzer.gui.scientific_projection import site_panels
from peanalyzer.workflow_storage import WorkflowError, owned, read_json

NATIVE = 'Original CRISPResso2 2.3.4 results'
DERIVED = 'PEAnalyzer-derived CRISPResso allele measurements'
INDEPENDENT = 'Independent PEAnalyzer sequence measurements'
QC = 'Reconciliation and scientific QC'
GROUPS = (NATIVE, DERIVED, INDEPENDENT, QC)
COLUMNS = ('sample_id','target','analysis_mode','measurement_source','measurement','definition','population',
           'copy','reference','integer_count','observation','numerator','denominator','fraction','eligibility','reasons',
           'native_execution_id','execution_status','extraction_status','recount_status','runtime_identity_status','direct_parity_status',
           'source_artifact','source_sha256')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ratio(n, d):
    return n, d, n/d if n is not None and d else None


def make_document(output, result):
    output = Path(output)
    native = read_json(owned(output,'native_runs.json'))
    sources = {'result.json': digest(owned(output,'result.json')), 'native_runs.json': digest(owned(output,'native_runs.json'))}
    rows = []
    mode = getattr(result, 'analysis_mode', 'precise_edit')
    base = dict(sample_id=result.sample_id,target=result.target_id,analysis_mode=mode)
    def add(group, measurement, definition, population, *, source='result.json', copy=None, ref=None,
            status='REPORTABLE', reasons=(), count=None, observation=None, value=(None,None,None), run=None):
        run = run or {}
        n,d,f = value
        rows.append({**base,'measurement_source':group,'measurement':measurement,'definition':definition,
                     'population':population,'copy':copy,'reference':ref,'integer_count':count,'observation':observation,
                     'numerator':n,'denominator':d,'fraction':f,'eligibility':status,'reasons':list(reasons),
                     'native_execution_id':run.get('id'),'execution_status':run.get('execution_status'),
                     'extraction_status':run.get('extraction_status'),'recount_status':run.get('recount_status'),
                     'runtime_identity_status':run.get('runtime_identity_status'),'direct_parity_status':run.get('direct_parity_status'), 'source_artifact':source,
                     'source_sha256':sources[source]})
    def native_row(run, name, definition, **kw):
        reasons = list(kw.pop('reasons', ()))
        status = kw.pop('status', 'REPORTABLE')
        if run['population'] == 'confident_copy_cohort':
            gate = getattr(result,'anchor_evidence',{}).get('copy_routing_eligibility',{})
            affected = gate.get('reason_codes',{}).get(run.get('copy'),[])
            if affected:
                reasons.extend(affected)
                if status == 'REPORTABLE':
                    status = 'BIOLOGICAL_INTERPRETATION_BLOCKED'
        if run.get('runtime_identity_status') != 'VERIFIED':
            reasons.append('UNQUALIFIED_RUNTIME')
            if status == 'REPORTABLE':
                status = 'UNQUALIFIED_RUNTIME'
        add(NATIVE,name,definition,run['population'],source='native_runs.json',copy=run.get('copy'),run=run,status=status,reasons=list(dict.fromkeys(reasons)),**kw)
    for run in native['runs']:
        extracted = run['extraction_status']=='PASS'
        add(QC,'Native execution and reconciliation','Stored execution, extraction, original allele-table recount and direct reproduction states.',
            run['population'],source='native_runs.json',copy=run.get('copy'),run=run,status=run['execution_status'],reasons=run['reasons'])
        for ref,positions in run.get('include_idxs',{}).items():
            add(QC,'Effective quantification window','Zero-based included positions recorded by the native executable.',
                run['population'],source='native_runs.json',copy=run.get('copy'),ref=ref,run=run,
                observation=json.dumps(positions),status=run['extraction_status'])
        if not extracted:
            native_row(run,'Native measurements','Native extraction did not produce verified counts.',status=run['extraction_status'],reasons=run['reasons'])
            continue
        for k,v in run['counts'].items():
            if k not in ('numerator','denominator'):
                native_row(run,k,'Integer reconciled to the native mapping or alignment output.',count=v)
        for ref,counts in run['per_reference'].items():
            for k,v in counts.items():
                native_row(run,k,'Integer in the native per-reference quantification table.',ref=ref,count=v)
        if 'numerator' in run['counts']:
            counts = run['counts']
            native_row(run,'Prime-edited reference fraction','Reads assigned to Prime-edited divided by all native aligned reads.',
                       ref='Prime-edited',value=ratio(counts['numerator'],counts['denominator']),
                       status='REPORTABLE' if counts['denominator'] else 'NOT_ASSESSABLE',
                       reasons=[] if counts['denominator'] else ['NO_ALIGNED_READS'])
    if not native['runs']:
        add(NATIVE,'Native execution','No native execution is recorded for this sample and target.','all_prepared_pairs',
            source='native_runs.json',status='NOT_RUN',reasons=native['reasons'])
    if mode == 'precise_edit':
        exact = [result.target_metrics.total_precise_pe, *(c.precise for c in result.copies.values())]
        for rec in exact:
            add(INDEPENDENT,rec.metric_name,'Exact intended products divided by exact WT plus exact intended products, subject to the stored population eligibility.',rec.population_scope,
                copy=rec.copy_id,value=ratio(rec.numerator,rec.denominator),status=rec.status,reasons=rec.reason_codes)
            if rec.products:
                for field in ('exact_wt','exact_pe','denominator_exclusions','unresolved_unassessable'):
                    add(QC,field,'Diagnostic observed count in the canonical classification population.',
                        rec.population_scope,copy=rec.copy_id,count=getattr(rec.products,field),status=rec.status,reasons=rec.reason_codes)
        for copy,anchor in result.anchor_evidence.get('backend_metrics',{}).items():
            insertion = anchor.get('insertion_products')
            if insertion:
                for name,n in insertion['counts'].items():
                    add(DERIVED,'Insertion product · '+name,insertion['method'],insertion['scope'],ref=copy,count=n)
        for scope, policies in result.derived_metrics.items():
            for policy,rec in policies.items():
                add(INDEPENDENT,'Family tolerance · '+policy,'PE-family products divided by WT-family plus PE-family products under the named policy.',
                    scope,copy=rec.copy_id,value=ratio(rec.numerator,rec.denominator),status=rec.status,reasons=rec.reason_codes)
        routes = result.anchor_evidence.get('copy_routing_eligibility',{})
        for copy,reasons in routes.get('reason_codes',{}).items():
            add(QC,'Copy routing eligibility','Evaluation of copy retention for observed paired read lengths.',
                'confident_copy_cohort',copy=copy,status='NOT_ASSESSABLE' if reasons else 'PASS',reasons=reasons)
        for copy, ext in result.anchor_evidence.get('extension_alleles',{}).items():
            for k,v in ext.get('counts',{}).items():
                add(DERIVED,k,'Extension allele class from a conventional WT-reference alignment.', 'confident_copy_cohort',
                    copy=copy,count=v,status=ext['status'],reasons=ext.get('reason_codes',[]))
        site_path = owned(output, 'intended_sites.json')
        if site_path.exists():
            src = site_path.name
            sources[src] = digest(site_path)
            source = Source(name=src,artifact_id='sites',sha256=sources[src],size_bytes=str(site_path.stat().st_size),kind='json',downloadable=True)
            raw = read_json(site_path)
            for p in site_panels(raw,source,result.sample_id,result.target_id,canonical_record=result.target_metrics.total_precise_pe):
                if p.method=='Exact WT or intended product':
                    continue
                group = DERIVED if 'CRISPResso' in p.method else INDEPENDENT if p.measurements else QC
                copy = p.population.removeprefix('Copy · ') if p.population.startswith('Copy · ') else None
                run = next((r for r in native['runs'] if r['id']=='core_sites'),None) if 'CRISPResso' in p.method else None
                ref = p.population.removeprefix('Alignment to ').removesuffix(' reference') if p.population.startswith('Alignment to ') else None
                for m in p.measurements:
                    value = tuple(None if v is None else int(v) for v in (m.numerator,m.denominator)) + (m.fraction,)
                    unavailable = m.fraction is None and p.status in ('ASSESSED','REPORTABLE')
                    add(group,p.method+' · '+m.name,p.definition,p.population,source=src,copy=copy,ref=ref,
                        value=value,status='NOT_ASSESSABLE' if unavailable else p.status,
                        reasons=['NO_ASSESSABLE_DENOMINATOR'] if unavailable else p.reasons,run=run)
                if not p.measurements or p.evidence:
                    for f in p.evidence:
                        if f.name in ('WT','A_only','B_only','AB','other_mixed','unassessable','Assessable pairs') or f.name.startswith(('qc · ','site_exclusions · ','site_orientation · ')):
                            if f.value is not None and f.value.isascii() and f.value.isdecimal():
                                add(group,p.method+' · '+f.name,p.definition,p.population,source=src,copy=copy,ref=ref,
                                    count=int(f.value),status=p.status,reasons=p.reasons,run=run)
                        elif not p.measurements:
                            add(QC,p.method+' · '+f.name,'Stored sample assessment evidence.',p.population,
                                source=src,copy=copy,ref=ref,observation=f.value,status=p.status,reasons=p.reasons,run=run)
                if p.reasons:
                    add(QC,p.method,p.definition,p.population,source=src,copy=copy,ref=ref,status=p.status,reasons=p.reasons,run=run)
    elif result.metric_contract_version != 'empty-nuclease-control-v1':
        multi = hasattr(result,'combined')
        populations = [(None,result.combined),*result.copies.items()] if multi else [(result.target.copy_name,result)]
        for copy, record in populations:
            for k,v in record.metrics.items():
                add(DERIVED,k,'Reads with the named window outcome divided by the assessable aligned reads in this population.',
                    'confident_copy_cohort' if multi and copy else 'combined_target' if multi else 'single_copy_identity',
                    copy=copy,value=(v.numerator,v.denominator,v.fraction),status=record.status,reasons=record.reason_codes)
        for reason,count in (getattr(result,'aligned_exclusion_reasons',None) or {}).items():
            add(QC,reason,'Aligned reads excluded from the selected window assessment.','combined_target',count=count)
    qc_path = owned(output,'sample_qc.json')
    if qc_path.exists():
        sources[qc_path.name] = digest(qc_path)
        qc = read_json(qc_path)
        add(QC,'Prepared read depth',f"Configured minimum {qc['minimum_prepared_read_pairs']} prepared pairs. Sample role {qc['sample_role']}.",
            'all_prepared_pairs',source=qc_path.name,count=qc['prepared_read_pairs'],status=qc['depth_status'])
    return dict(contract='measurement-catalog-v1',**base,rows=rows,native_source='native_runs.json',
                native_source_sha256=sources['native_runs.json'],
                native_artifacts=[dict(id=r['id'],paths=r['paths'],sha256=r['sha256']) for r in native['runs']])


def rendered(doc):
    out = io.StringIO(newline='')
    writer = csv.writer(out,delimiter='\t',lineterminator='\n')
    writer.writerow(COLUMNS)
    def cells(row):
        return [', '.join(row[k]) if k=='reasons' else row[k] for k in COLUMNS]
    for row in doc['rows']:
        writer.writerow(cells(row))
    page = ['<!doctype html><html lang="en"><meta charset="utf-8"><title>Sample measurements</title>',
            '<h1>'+html.escape(doc['sample_id']+' · '+doc['target'])+'</h1>',
            '<p>Fractions are stored on a scale from 0 to 1. Missing ratios have no numeric value.</p>']
    for group in GROUPS:
        page.extend(['<h2>'+html.escape(group)+'</h2>','<table><thead><tr>',
                     *(f'<th scope="col">{k}</th>' for k in COLUMNS),'</tr></thead><tbody>'])
        for row in doc['rows']:
            if row['measurement_source']==group:
                page.append('<tr>'+''.join(f'<td>{html.escape(str(v)) if v is not None else "—"}</td>' for v in cells(row))+'</tr>')
        page.append('</tbody></table>')
    page.append('<h2>Native reproduction and original artifacts</h2>')
    for run in doc['native_artifacts']:
        page.append('<h3>'+html.escape(run['id'])+'</h3><ul>')
        for role, path in run['paths'].items():
            page.append('<li><a href="./'+html.escape(path,quote=True)+'">'+html.escape(role)+'</a> · '+html.escape(path)+'</li>')
        page.append('</ul>')
    page.append('</html>')
    return {'measurements.json':json.dumps(doc,indent=2,allow_nan=False)+'\n',
            'measurements.tsv':out.getvalue(),'measurements.html':'\n'.join(page)}


def write_measurement_exports(output,result):
    for name,contents in rendered(make_document(output,result)).items():
        with owned(Path(output),name).open('x',encoding='utf-8',newline='') as stream:
            stream.write(contents)


def verify_measurement_exports(output,result):
    for name,contents in rendered(make_document(output,result)).items():
        if owned(Path(output),name).read_bytes()!=contents.encode():
            raise WorkflowError('MEASUREMENT_EXPORT_MISMATCH',name)
