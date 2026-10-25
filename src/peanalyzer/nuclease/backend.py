"""Pinned single-reference Core execution and authoritative allele reconciliation."""
import csv
import io
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from peanalyzer.analysis_verify import verify_analysis_output
from peanalyzer.backend.pooled import BackendError,utc_now
from peanalyzer.backend.metrics import COUNTERS,integer,table,child_file,aligned_partition
from peanalyzer.backend.comparator import normalize_include_idxs
from peanalyzer.demux_verify import read_json,sha256_file
from peanalyzer.metrics.production import RUNTIME_DIGEST,digest
from peanalyzer.provenance import software_provenance
from peanalyzer.nuclease.models import allele,aggregate,NucleaseMetricResult,Provenance
from peanalyzer.nuclease.targets import NucleaseTarget

LIMITATIONS=[
    'CRISPResso2 2.3.4 is the sole variant caller. Counts and net sizes are quantification-window specific.',
    'MULTICOPY_NUCLEASE_UNSUPPORTED: only single-copy panels are qualified; PE routing is never used.',
    'Demultiplexing, preparation and backend preprocessing/alignment define the available population; unaligned causes are unknown unless demonstrated.',
    'Substitution position spectra are deferred; authoritative detailed event fields and count-level metrics are retained.',
    'This analysis uses CRISPResso2 with an explicit quantification window derived from the experimentally mapped/reported TIGR–Tas cleavage geometry when tigr_tas_v1 is selected. It does not reproduce unpublished paper options.',
    'No automatic biological interpretation; net-zero indel alleles remain indels.'
]


def parse_nuclease_child(root,target,expected_pairs):
    """Read integer calls, never infer events from aligned strings or FASTQs."""
    root=Path(root);data=read_json(root/'CRISPResso2_info.json');running=data['running_info']
    if running['version']!='2.3.4' or not running.get('end_time_string'):raise ValueError('UNQUALIFIED_OR_INCOMPLETE_BACKEND')
    namespace=running['args']
    if namespace.get('_type')!='argparse.Namespace':raise ValueError('BACKEND_ARGUMENTS_INVALID')
    arguments=namespace['value']
    for flag in ('ignore_substitutions','ignore_insertions','ignore_deletions','use_legacy_insertion_quantification',
                 'expand_ambiguous_alignments','assign_ambiguous_alignments_to_first_reference','crispresso1_mode'):
        if arguments.get(flag) is not False:raise ValueError('UNQUALIFIED_NUCLEASE_CONFIGURATION: '+flag)
    if (arguments.get('write_detailed_allele_table') is not True or arguments.get('amplicon_seq')!=target.wt_sequence
        or arguments.get('quantification_window_coordinates')!=target.window['coordinates']
        or arguments.get('guide_seq') or any(arguments.get(k) for k in ('prime_editing_pegRNA_spacer_seq',
            'prime_editing_pegRNA_extension_seq','prime_editing_pegRNA_scaffold_seq','prime_editing_nicking_guide_seq',
            'prime_editing_override_prime_edited_ref_seq'))):raise ValueError('BACKEND_CONFIGURATION_MISMATCH')
    if any(arguments.get(k)!=v or type(arguments.get(k)) is not type(v) for k,v in target.scientific_identity['backend_settings'].items()):
        raise ValueError('BACKEND_CONFIGURATION_MISMATCH')
    refs=data['results']['refs']
    if set(refs)!={'Reference'} or refs['Reference']['sequence']!=target.wt_sequence:raise ValueError('BACKEND_REFERENCE_MISMATCH')
    expected=sorted(p for a,b in target.window['intervals'] for p in range(a,b+1))
    if normalize_include_idxs(refs['Reference']['include_idxs'],len(target.wt_sequence))!=expected:raise ValueError('BACKEND_WINDOW_MISMATCH')
    counters={k:integer(running['alignment_stats'][k]) for k in COUNTERS}
    aligned=counters['N_CACHED_ALN']+counters['N_COMPUTED_ALN'];unaligned=counters['N_CACHED_NOTALN']+counters['N_COMPUTED_NOTALN']
    if counters['N_TOT_READS']!=aligned+unaligned:raise ValueError('ALIGNMENT_COUNTER_RECONCILIATION_FAILED')
    mapping_rows=table(child_file(root,running['mapping_stats_filename']))
    if len(mapping_rows)!=1:raise ValueError('invalid mapping row inventory')
    mapping={k:integer(v) for k,v in mapping_rows[0].items()}
    if (mapping['READS IN INPUTS']!=expected_pairs or mapping['READS AFTER PREPROCESSING']!=counters['N_TOT_READS']
        or mapping['READS ALIGNED']!=aligned or expected_pairs<counters['N_TOT_READS']
        or any(mapping[k]!=counters[k] for k in COUNTERS[1:])):raise ValueError('MAPPING_RECONCILIATION_FAILED')
    totals={k:integer(v) for k,v in data['results']['alignment_stats']['counts_total'].items()}
    if set(totals)!={'Reference'}:raise ValueError('unexpected reference totals')
    quant=table(child_file(root,running['quant_of_editing_freq_filename']))
    discarded=integer(data['results']['alignment_stats']['counts_discarded']['Reference'])
    if (len(quant)!=1 or quant[0]['Amplicon']!='Reference' or integer(quant[0]['Reads_aligned_all_amplicons'])!=aligned
        or integer(quant[0]['Reads_aligned'])!=totals['Reference'] or integer(quant[0]['Reads_in_input'])!=expected_pairs
        or integer(quant[0]['Discarded'])!=discarded):raise ValueError('QUANTIFICATION_RECONCILIATION_FAILED')
    with zipfile.ZipFile(child_file(root,running['allele_frequency_table_zip_filename'])) as archive:
        name=running['allele_frequency_table_filename']
        if Path(name).name!=name or archive.namelist().count(name)!=1:raise ValueError('invalid allele archive member')
        with archive.open(name) as stream:
            reader=csv.DictReader(io.TextIOWrapper(stream),delimiter='\t')
            if not reader.fieldnames or len(reader.fieldnames)!=len(set(reader.fieldnames)):raise ValueError('invalid allele header')
            rows=list(reader)
    alleles=[allele(r) for r in rows]
    if any(a.authoritative_fields['Reference_Sequence'].replace('-','')!=target.wt_sequence for a in alleles):raise ValueError('ALLELE_REFERENCE_MISMATCH')
    partition=aligned_partition(data,rows,totals)
    if sum(partition.values())!=aligned:raise ValueError('ALIGNED_PARTITION_MISMATCH')
    counts,metrics,sizes=aggregate(alleles,aligned)
    if counts['unmodified']!=integer(quant[0]['Unmodified']) or sum(counts[k] for k in ('substitution_only','indel_only','indel_plus_substitution'))!=integer(quant[0]['Modified']):
        raise ValueError('ALLELE_MODIFIED_RECONCILIATION_FAILED')
    return dict(backend_input_reads=expected_pairs,reads_after_preprocessing=counters['N_TOT_READS'],
        aligned_reads=aligned,unaligned_reads=unaligned,alignment_counters=counters,mapping_statistics=mapping,
        class_counts=counts,metrics=metrics,fraction_of_indel_reads_by_net_size=sizes,alleles=alleles)


def run_nuclease_metrics(*,analysis_root,sample_id,targets,analysis_id,output,core,runtime_digest):
    if len(targets)!=1:raise ValueError('MULTICOPY_NUCLEASE_UNSUPPORTED')
    target=NucleaseTarget.model_validate(targets[0].model_dump())
    if core.version!='2.3.4' or runtime_digest!=RUNTIME_DIGEST:raise ValueError('UNQUALIFIED_BACKEND_RUNTIME')
    verified=verify_analysis_output(Path(analysis_root));sample=verified.manifest['samples'][sample_id]
    output=Path(output).absolute()
    if output.exists() or output.is_symlink():raise ValueError('output must be new')
    output.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.'+output.name+'.incomplete-',dir=output.parent))
    try:
        for mate in (1,2):
            entry=sample['files'][f'r{mate}'];dest=stage/f'input_R{mate}.fastq.gz'
            shutil.copyfile(verified.root/entry['path'],dest)
            if sha256_file(dest)!=entry['sha256']:raise ValueError('SOURCE_CHANGED')
        argv=[core.path,'-r1','input_R1.fastq.gz','-r2','input_R2.fastq.gz','--amplicon_seq',target.wt_sequence,
            '--quantification_window_coordinates',target.window['coordinates'],
            '--exclude_bp_from_left','0','--exclude_bp_from_right','0',
            '--name','nuclease','--output_folder','output','--write_detailed_allele_table',
            '--keep_intermediate','--suppress_report','--suppress_plots']
        execution=dict(analysis_mode='indel_nuclease',identity_mechanism='single_copy_identity',
            scientific_identity=target.scientific_identity,argv=argv,cwd=str(stage),software=software_provenance(),
            runtime_digest=runtime_digest,version_probe=core.probe,started_at=utc_now(),status='running')
        with (stage/'stdout.txt').open('w') as out,(stage/'stderr.txt').open('w') as err:
            result=subprocess.run(argv,cwd=stage,stdout=out,stderr=err,check=False)
        execution.update(return_code=result.returncode,ended_at=utc_now())
        if result.returncode:raise BackendError('COMMAND_FAILED',f'nuclease Core exit {result.returncode}: '+(stage/'stderr.txt').read_text()[-2000:])
        child=stage/'output/CRISPResso_on_nuclease'
        before={p.relative_to(stage).as_posix():sha256_file(p) for p in sorted(stage.rglob('*')) if p.is_file()}
        parsed=parse_nuclease_child(child,target,sample['pairs'])
        if before!={p.relative_to(stage).as_posix():sha256_file(p) for p in sorted(stage.rglob('*')) if p.is_file()}:raise ValueError('BACKEND_SOURCE_CHANGED')
        execution['resolved_backend_arguments']=read_json(child/'CRISPResso2_info.json')['running_info']['args']['value']
        if verify_analysis_output(Path(analysis_root)).manifest_sha256!=verified.manifest_sha256:raise ValueError('SOURCE_CHANGED')
        execution['status']='completed'
        (stage/'execution.json').write_text(json.dumps(execution,indent=2,sort_keys=True)+'\n')
        artifacts={p.relative_to(stage).as_posix():sha256_file(p) for p in sorted(stage.rglob('*')) if p.is_file()}
        import hashlib
        metric=NucleaseMetricResult(sample_id=sample_id,target_id=target.target_name,analysis_id=analysis_id,target=target,
            status='REPORTABLE' if parsed['aligned_reads'] else 'NOT_ASSESSABLE',reason_codes=[] if parsed['aligned_reads'] else ['NO_ALIGNED_READS'],
            **parsed,provenance=Provenance(target_definitions_sha256=digest([target.model_dump()]),
                wt_sha256=hashlib.sha256(target.wt_sequence.encode()).hexdigest(),prepared_manifest_sha256=verified.manifest_sha256,
                prepared_sample=sample,runtime_digest=runtime_digest,crispresso_version=core.version,
                scientific_identity=target.scientific_identity,execution=execution,artifacts=artifacts),limitations=LIMITATIONS)
        (stage/'result.json').write_text(metric.model_dump_json(indent=2)+'\n')
        (stage/'execution_failures.json').write_text('{}\n')
        if output.exists() or output.is_symlink():raise ValueError('output appeared during execution')
        stage.rename(output)
        return metric
    finally:
        if stage.exists():shutil.rmtree(stage)
