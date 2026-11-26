"""Copy-conditioned exact haplotypes from a separate guide-free conventional Core run.

The native PE reference model is inapplicable to a copy with a confirmed
polymorphism in the experimental extension. Independent routing markers must
establish copy identity before this WT-only alignment is authorized.
"""
import json
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from peanalyzer.backend.core import verify_routing_output
from peanalyzer.geometry import geometry
from peanalyzer.schemas import Target
from peanalyzer.routing import RoutingPolicy, policy_identity
from peanalyzer.backend.intended_sites import iter_alleles
from peanalyzer.backend.metrics import COUNTERS, aligned_partition, child_file, integer, table
from peanalyzer.backend.pooled import VERSION, BackendError, utc_now
from peanalyzer.demux_verify import read_json, sha256_file
from peanalyzer.docker_runtime import IMAGE


CLASSES = ('exact_wt', 'intended_snp_retained', 'intended_snp_converted', 'other_modification', 'unresolved')


def _argv(target):
    return ['-r1','input_R1.fastq.gz','-r2','input_R2.fastq.gz','--amplicon_seq',target.wt_sequence,
            '--name','extension_alleles','--output_folder','output','--write_detailed_allele_table']


def _states(target, extension):
    if extension['status'] != 'copy_polymorphism' or not extension['mismatches']:
        raise ValueError('A copy-specific experimental extension mismatch must be established')
    converted = list(target.prime_edited_sequence)
    for mismatch in extension['mismatches']:
        pos = mismatch['original_pe_position']
        if not mismatch['natural_copy_snp'] or converted[pos] != mismatch['observed']:
            raise ValueError('Unverified natural copy polymorphism')
        converted[pos] = mismatch['expected']
    states = {target.wt_sequence: 'exact_wt', target.prime_edited_sequence: 'intended_snp_retained',
              ''.join(converted): 'intended_snp_converted'}
    if len(states) != 3:
        raise ValueError('Contradictory extension-associated haplotype definitions')
    return states


def run_extension(root, target, extension, cohort, routing_root, core, digest):
    root, routing_root = Path(root), Path(routing_root)
    if digest != IMAGE or core.version != VERSION or not cohort['pairs']:
        raise ValueError('Verified nonempty cohort and qualified Core 2.3.4 runtime required')
    routing = verify_routing_output(routing_root)
    if routing['copy_routing_eligibility']['reason_codes'][target.copy_name]:
        raise ValueError('State-selective copy cohorts cannot support extension haplotype efficiencies')
    panel = [Target.model_validate(t) for t in routing['targets']]
    copy_info = geometry(panel)['copies'][target.copy_name]['native_reference']
    if (routing['policy_identity'] != policy_identity(RoutingPolicy()) or target not in panel
            or routing['cohorts'][target.copy_name] != cohort or copy_info['extension_match'] != extension):
        raise ValueError('Verified routing, copy and extension identities are required')
    _states(target, extension)
    root.parent.mkdir(parents=True, exist_ok=True)
    root.mkdir()
    with tempfile.TemporaryDirectory(prefix='pe-extension-') as tmp:
        work = Path(tmp)
        for mate in ('r1','r2'):
            f = cohort['files'][mate]
            path = work / f'input_{mate.upper()}.fastq.gz'
            shutil.copyfile(routing_root/f['path'], path)
            if sha256_file(path) != f['sha256']:
                raise ValueError('Routing cohort input changed')
        argv = [core.path, *_argv(target)]
        execution = dict(argv=argv, runtime_digest=digest, version_probe=core.probe,
                         routing_manifest_sha256=sha256_file(routing_root/'routing_manifest.json'),
                         copy=target.copy_name, inputs=cohort, extension=extension, started_at=utc_now(),status='running')
        try:
            with (work/'stdout.txt').open('w') as out, (work/'stderr.txt').open('w') as err:
                run = subprocess.run(argv, cwd=work, stdout=out, stderr=err, check=False)
            execution['return_code'] = run.returncode
            if run.returncode:
                raise BackendError('COMMAND_FAILED',f'Conventional Core exited with {run.returncode}')
            execution['status'] = 'completed'
        finally:
            execution['ended_at'] = utc_now()
            (work/'execution.json').write_text(json.dumps(execution,indent=2)+'\n')
            shutil.copytree(work, root, dirs_exist_ok=True)


def read_extension(root, target, extension, cohort, routing_hash, digest):
    """Verify source FASTQ identity, exact observed products and the whole population."""
    root = Path(root)
    states = _states(target, extension)
    ex = read_json(root/'execution.json')
    if (root.is_symlink() or ex['status'] != 'completed' or ex['return_code'] != 0
            or digest != IMAGE or ex['runtime_digest'] != digest or ex['argv'][1:] not in (_argv(target), _argv(target)+['--suppress_report','--suppress_plots'])
            or ex['routing_manifest_sha256'] != routing_hash or ex['copy'] != target.copy_name
            or ex['inputs'] != cohort or ex['extension'] != extension):
        raise ValueError('Extension allele execution identity mismatch')
    paths = [root/'execution.json']
    for mate in ('r1','r2'):
        f = cohort['files'][mate]
        path = root/f'input_{mate.upper()}.fastq.gz'
        if path.is_symlink() or path.stat().st_size != f['size_bytes'] or sha256_file(path) != f['sha256']:
            raise ValueError('Extension allele cohort identity mismatch')
        paths.append(path)
    child = root/'output/CRISPResso_on_extension_alleles'
    if child.is_symlink() or child.parent.is_symlink():
        raise ValueError('Invalid Core output location')
    info_path = child_file(child,'CRISPResso2_info.json')
    info = read_json(info_path)
    running, results = info['running_info'], info['results']
    args = running['args']['value']
    if (running['version'] != VERSION or not running.get('end_time_string')
            or set(results['refs']) != {'Reference'} or results['refs']['Reference']['sequence'] != target.wt_sequence
            or args['expand_ambiguous_alignments'] or args['assign_ambiguous_alignments_to_first_reference']
            or not args['write_detailed_allele_table'] or args['prime_editing_pegRNA_extension_seq']):
        raise ValueError('A conventional, exclusive single-WT alignment is required')
    mapping, = table(child_file(child,running['mapping_stats_filename']))
    raw, merged, aligned = [integer(mapping[k]) for k in ('READS IN INPUTS','READS AFTER PREPROCESSING','READS ALIGNED')]
    stats = {k:integer(running['alignment_stats'][k]) for k in COUNTERS}
    if (raw != cohort['pairs'] or not aligned <= merged <= raw or stats['N_TOT_READS'] != merged
            or stats['N_CACHED_ALN'] + stats['N_COMPUTED_ALN'] != aligned
            or sum(stats[k] for k in COUNTERS[1:]) != merged
            or any(integer(mapping[k]) != stats[k] for k in COUNTERS[1:])):
        raise ValueError('Input and alignment counts disagree')
    totals = {k:integer(v) for k,v in results['alignment_stats']['counts_total'].items()}
    quant, = table(child_file(child,running['quant_of_editing_freq_filename']))
    if (set(totals) != {'Reference'} or quant['Amplicon'] != 'Reference'
            or integer(quant['Reads_in_input']) != raw or integer(quant['Reads_aligned_all_amplicons']) != aligned
            or integer(quant['Reads_aligned']) != totals['Reference']
            or integer(quant['Discarded']) != integer(results['alignment_stats']['counts_discarded']['Reference'])):
        raise ValueError('Native quantification integers disagree')
    counts, reference_counts = Counter(), Counter()
    for row in iter_alleles(child, running):
        name, n = row['Reference_Name'], integer(row['#Reads'])
        reference_counts[name] += n
        query, ref = row['Aligned_Sequence'], row['Reference_Sequence']
        label = 'unresolved'
        if name == 'Reference':
            if len(ref) != len(query) or ref.replace('-','') != target.wt_sequence:
                raise ValueError('Malformed alignment for secondary copy')
            sequence = query.replace('-','')
            if sequence and set(sequence) <= set('ACGT') and not query.startswith('-') and not query.endswith('-'):
                label = states.get(sequence,'other_modification')
        counts[label] += n
    partition = aligned_partition(info, ({'Reference_Name':k,'#Reads':n} for k,n in reference_counts.items()), totals)
    if sum(counts.values()) != aligned or sum(partition.values()) != aligned:
        raise ValueError('Conventional alignment and haplotype totals disagree')
    # Reads lost during merging or alignment retain their own unresolved population.
    counts['unresolved'] += raw - aligned
    paths.extend([info_path, *(child_file(child,running[k]) for k in
                 ('mapping_stats_filename','quant_of_editing_freq_filename','allele_frequency_table_zip_filename'))])
    return dict(status='REPORTABLE', method='PEAnalyzer exact observed products from conventional single-WT Core alignments',
                scope='verified confidently routed copy cohort', input_pairs=raw, preprocessed=merged,aligned=aligned,
                preprocessing_loss=raw-merged,unaligned=merged-aligned,
                counts={k:counts[k] for k in CLASSES}, extension=extension,
                artifacts={str(p.relative_to(root)):sha256_file(p) for p in paths})
