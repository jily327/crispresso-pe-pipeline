"""Nuclease presentation of stored results, without variant calling or inference."""
import html

def extend_html(page,spec):
    from peanalyzer.reporting import _table,percentage,canonical
    start=page.index('<h2>Measurement definitions</h2>');end=page.index('<h2>Biological sample summaries</h2>',start)
    definition='<h2>Measurement definitions</h2><p>Indel/nuclease mode. CRISPResso2 2.3.4 is the authoritative variant caller. Primary indel fraction counts each aligned read with n_inserted &gt; 0 OR n_deleted &gt; 0 once, divided by authoritative aligned reads. Substitutions remain enabled. Biological samples, never reads, are inference units. Net size is inserted minus deleted bases within the CRISPResso quantification-window contract.</p>'
    page=page[:start]+definition+page[end:]
    parts=['<h2>Nuclease evidence</h2><p>The tigr_tas_v1 primary window is W2: the zero-based inclusive 10-bp cut span s+4 through s+13. W1, W3 and W4 are qualified sensitivity windows unless explicitly selected. Physical cut pairs and orientation-aware labels are recorded separately below.</p>']
    for result in spec['nuclease_results']:
        parts.append('<h3>'+html.escape(result['sample_id']+' / '+result['target_id'])+'</h3>')
        rows=[dict(metric=k,**v,percentage=percentage(v['fraction'])) for k,v in result['metrics'].items()]
        parts.append(_table('Exact CRISPResso-derived counts',rows,['metric','numerator','denominator','fraction','percentage']))
        parts.append(_table('Scientific configuration',[result['provenance']['scientific_identity']],list(result['provenance']['scientific_identity'])))
        parts.append(_table('Backend population and provenance',[dict(identity_mechanism=result['identity_mechanism'],
            backend_input_reads=result['backend_input_reads'],reads_after_preprocessing=result['reads_after_preprocessing'],
            aligned_reads=result['aligned_reads'],unaligned_reads=result['unaligned_reads'],class_counts=result['class_counts'],
            crispresso_version=result['provenance']['crispresso_version'],runtime_digest=result['provenance']['runtime_digest'])],
            ['identity_mechanism','backend_input_reads','reads_after_preprocessing','aligned_reads','unaligned_reads','class_counts','crispresso_version','runtime_digest']))
        sizes=[dict(net_delta_bp=k,**v) for k,v in result['fraction_of_indel_reads_by_net_size'].items()]
        parts.append(_table('Fraction of indel reads by NET size',sizes,['net_delta_bp','numerator','denominator','fraction']))
        alleles=sorted(result['alleles'],key=lambda a:(-a['reads'],canonical(a['authoritative_fields'])))
        rows=[dict(**a['authoritative_fields'],net_delta_bp=a['net_delta_bp'],product_class=a['product_class']) for a in alleles[:20]]
        parts.append(_table('Top 20 CRISPResso allele rows; all rows retained in source/result.json',rows,
            ['Aligned_Sequence','Reference_Sequence','#Reads','%Reads','n_inserted','n_deleted','n_mutated','net_delta_bp','Read_Status','Reference_Name','product_class']))
        parts.append('<ul>'+''.join('<li>'+html.escape(s)+'</li>' for s in result['limitations'])+'</ul>')
    page=page.replace('<li>Copy metrics are routing-conditioned.</li>', '<li>Single-copy nuclease identity is experimental; all prepared pairs enter the backend.</li>')
    page=page.replace('<li>M4 upstream observability and read-geometry limitations remain upstream.</li>', '<li>CRISPResso preprocessing and alignment acceptance determine backend attrition.</li>')
    return page.replace('</main>', ''.join(parts)+'</main>')
