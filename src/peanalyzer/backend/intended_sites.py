"""Two-site measurements derived from exclusive, conventional Core 2.3.4 alignments.

Each ordinary allele contributes its integer abundance once. Per-reference totals
describe Core's assignment and are never asserted to identify biological copies.
"""
import csv
import io
import json
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from peanalyzer.backend.comparator import normalize_include_idxs
from peanalyzer.backend.metrics import COUNTERS, aligned_partition, child_file, fraction, integer, table
from peanalyzer.backend.pooled import BackendError, VERSION, utc_now
from peanalyzer.demux_verify import read_json, sha256_file
from peanalyzer.docker_runtime import IMAGE
from peanalyzer.haplotypes import build_panel

STATES = ('WT', 'A_only', 'B_only', 'AB', 'other_mixed', 'unassessable')
QC_FIELDS = ('additional_substitution', 'additional_indel', 'incomplete_or_unknown',
             'AB_with_additional_change', 'AB_full_length_exact', 'nonunique_site_deletion')


class UnqualifiedSiteBackend(ValueError):
    """A known design or runtime cannot support this supplementary measurement."""

    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _panel(targets):
    """Establish homologous site order and strand despite remote SNPs/indels."""
    targets = tuple(targets)
    by_name = {t.copy_name: t for t in targets}
    names = set(by_name)
    if (len({n.casefold() for n in names}) != len(targets) or
            any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', n)
                or n.startswith(('AMBIGUOUS_', 'DISCARDED_')) for n in names)):
        raise ValueError('Invalid or duplicated backend reference name')
    copies = {n: {'WT': t.wt_sequence, 'PE': t.prime_edited_sequence} for n,t in by_name.items()}
    if len({p['WT'] for p in copies.values()}) != len(copies):
        raise UnqualifiedSiteBackend('INDISTINGUISHABLE_WT_REFERENCES', 'Core requires distinct WT references')
    panel = build_panel('intended_sites', copies, ())
    designs = {n: (p['WT'], p['PE'], panel.sites[n]) for n,p in copies.items()}
    return designs


def iter_alleles(root, running_info):
    """Read the authoritative table identified by a completed Core child."""
    with ZipFile(child_file(root, running_info['allele_frequency_table_zip_filename'])) as archive:
        name = running_info['allele_frequency_table_filename']
        if Path(name).name != name or archive.namelist().count(name) != 1:
            raise ValueError('Invalid allele archive member')
        with archive.open(name) as stream:
            reader = csv.DictReader(io.TextIOWrapper(stream), delimiter='\t')
            if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
                raise ValueError('Invalid allele table header')
            yield from reader


def _uncertain_deletions(ref, query, first, last, site_columns):
    """All equivalent placements of an internal deletion in an exact tandem repeat.

    Sliding across a mismatch, another gap or the covered read boundary would
    change the observed allele. Quarantine only sites that are sometimes deleted.
    """
    uncertain = set()
    for gap in re.finditer('-+', query):
        start, end = gap.span()
        if start <= first or end > last:
            continue
        length = end - start
        left = right = start
        while (left > first and query[left-1] == ref[left-1] == ref[left+length-1]
               and ref[left-1] != '-'):
            left -= 1
        while (right + length <= last and query[right+length] == ref[right+length] == ref[right]
               and ref[right] != '-'):
            right += 1
        for site, col in enumerate(site_columns):
            if left <= col < right + length and not right <= col < left + length:
                uncertain.add(site)
    return uncertain


def _state(bases, wt, pe, sites):
    if None in bases:
        return 'unassessable'
    if any(q not in (wt[i], pe[i]) for q, i in zip(bases, sites)):
        return 'other_mixed'
    return ('WT', 'A_only', 'B_only', 'AB')[(bases[0] == pe[sites[0]]) + 2 * (bases[1] == pe[sites[1]])]


def _observe(row, design, n, counts):
    wt, pe, sites = design
    ref, query = row['Reference_Sequence'], row['Aligned_Sequence']
    if (len(ref) != len(query) or ref.replace('-', '') != wt or set(query) - set('ACGTN-')
            or any(x == y == '-' for x, y in zip(ref, query))):
        raise ValueError('Allele alignment disagrees with the selected reference')
    first = len(query) - len(query.lstrip('-'))
    last = len(query.rstrip('-')) - 1
    bases, site_columns, pos = [], [], -1
    additional_indel = additional_sub = False
    incomplete = first > 0 or last < len(query) - 1 or 'N' in query
    for column, (r, q) in enumerate(zip(ref, query)):
        if r == '-':
            additional_indel = True
            continue
        pos += 1
        if pos in sites:
            site_columns.append(column)
            bases.append(q if first <= column <= last and q != 'N' else None)
        elif first <= column <= last:
            additional_indel |= q == '-'
            additional_sub |= q in 'ACGT' and q != r
    counts['fixed_' + _state(bases, wt, pe, sites)] += n
    uncertain = _uncertain_deletions(ref, query, first, last, site_columns) if '-' in query else set()
    for index in uncertain:
        bases[index] = None
    flags = [q == pe[i] for q, i in zip(bases, sites)]
    for site, base, edited in zip(('A', 'B'), bases, flags):
        if base is not None:
            counts['observed_' + site] += n
            counts['edited_' + site] += n * edited
    state = _state(bases, wt, pe, sites)
    counts[state] += n
    if None not in bases and any(flags):
        counts['any_edit'] += n
    for qc, flag in zip(QC_FIELDS, (additional_sub, additional_indel, incomplete,
                                    state == 'AB' and (additional_sub or additional_indel),
                                    ref == wt and query == pe, bool(uncertain))):
        counts[qc] += n * flag


def _summarize(counts):
    joint = sum(counts[s] for s in STATES[:-1])
    return dict(counts={k: counts[k] for k in STATES}, joint_assessable=joint,
                site_A=fraction(counts['edited_A'], counts['observed_A']),
                site_B=fraction(counts['edited_B'], counts['observed_B']),
                A_only=fraction(counts['A_only'], joint), B_only=fraction(counts['B_only'], joint),
                double_edit=fraction(counts['AB'], joint), any_edit=fraction(counts['any_edit'], joint),
                qc={k: counts[k] for k in QC_FIELDS})


def _ranges(value, length):
    if not re.fullmatch(r'\d+-\d+(?:_\d+-\d+)*', value):
        raise ValueError('Expected inclusive zero-based coordinate ranges joined by _')
    indices = []
    for span in value.split('_'):
        start, end = map(int, span.split('-'))
        if not 0 <= start <= end < length or (indices and start <= indices[-1]):
            raise ValueError('Quantification window outside WT reference or overlapping')
        indices.extend(range(start, end + 1))
    return indices


def _window_report(ref, design, requested):
    wt, _, sites = design
    actual = normalize_include_idxs(ref['include_idxs'], len(wt))
    if not actual:
        raise ValueError('Missing effective quantification window')
    # The special Core value "0" selects its default. Core also applies its
    # terminal exclusions to explicit intervals; record both requested and used.
    explicit = requested not in ('0', None, '')
    intended_window = _ranges(requested, len(wt)) if explicit else None
    outside = sorted(set(sites) - set(actual))
    if explicit and set(actual) - set(intended_window):
        raise ValueError('Backend expanded an explicit quantification window')
    return dict(requested=requested or None, source='explicit_coordinates' if explicit else 'backend_default',
                effective_indices=actual, intended_indices=list(sites), outside_window=outside,
                requested_indices_excluded=sorted(set(intended_window or []) - set(actual)),
                warning=('Native window statistics exclude at least one intended site. Review the '
                         'reported indices or select explicit coordinates for a separate run.') if outside else None)


def read_core_sites(root, targets, *, expected_input_pairs=None):
    """Validate genuine artifacts and derive counts independent of native PE-reference metrics."""
    root = Path(root)
    designs = _panel(targets)
    info = read_json(child_file(root, 'CRISPResso2_info.json'))
    running = info['running_info']
    if running['version'] != VERSION or not running.get('end_time_string'):
        raise ValueError('Unsupported or incomplete CRISPResso run')
    args = running['args']['value']
    if (not args['write_detailed_allele_table'] or args['expand_ambiguous_alignments']
            or args['assign_ambiguous_alignments_to_first_reference'] or not args['fastq_r2']):
        raise ValueError('Exclusive paired-end allele accounting required')
    ordered = args['amplicon_name'].split(',')
    refs = info['results']['refs']
    if set(refs) != set(designs) or len(ordered) != len(designs) or set(ordered) != set(designs):
        raise ValueError('Backend reference inventory mismatch')
    coords = args['quantification_window_coordinates']
    requested = coords.split(',') if coords else [''] * len(ordered)
    if len(requested) == 1 and requested[0] in ('0', ''):
        requested *= len(ordered)
    if len(requested) != len(ordered):
        raise ValueError('Missing per-reference window coordinates')
    windows = {}
    for name, coords in zip(ordered, requested):
        if refs[name]['sequence'] != designs[name][0]:
            raise ValueError('Backend WT reference sequence mismatch')
        windows[name] = _window_report(refs[name], designs[name], coords)

    mapping, = table(child_file(root, running['mapping_stats_filename']))
    raw, merged, aligned = [integer(mapping[k]) for k in
                            ('READS IN INPUTS', 'READS AFTER PREPROCESSING', 'READS ALIGNED')]
    counters = {k: integer(running['alignment_stats'][k]) for k in COUNTERS}
    if (not aligned <= merged <= raw or counters['N_TOT_READS'] != merged
            or counters['N_CACHED_ALN'] + counters['N_COMPUTED_ALN'] != aligned
            or sum(counters[k] for k in COUNTERS[1:]) != merged
            or any(integer(mapping[k]) != counters[k] for k in COUNTERS[1:])
            or (expected_input_pairs is not None and raw != integer(expected_input_pairs))):
        raise ValueError('Backend mapping and alignment counters disagree')
    stats = info['results']['alignment_stats']
    totals = {k: integer(v) for k, v in stats['counts_total'].items()}
    quant = table(child_file(root, running['quant_of_editing_freq_filename']))
    if set(totals) != set(designs) or len(quant) != len(designs) or {r['Amplicon'] for r in quant} != set(designs):
        raise ValueError('Quantification reference inventory mismatch')
    counts = {name: Counter() for name in designs}
    classes = Counter()
    native = Counter()
    for row in iter_alleles(root, running):
        name, n = row['Reference_Name'], integer(row['#Reads'])
        classes[name] += n
        if name in designs:
            _observe(row, designs[name], n, counts[name])
            native[name, row['Read_Status']] += n
    partition = aligned_partition(info, ({'Reference_Name': k, '#Reads': v} for k, v in classes.items()), totals)
    if sum(partition.values()) != aligned:
        raise ValueError('Nonexclusive aligned population')
    per_ref = {}
    for row in quant:
        name = row['Amplicon']
        if (integer(row['Reads_in_input']) != raw or integer(row['Reads_aligned_all_amplicons']) != aligned
                or integer(row['Reads_aligned']) != totals[name]
                or integer(row['Discarded']) != integer(stats['counts_discarded'][name])):
            raise ValueError('Quantification table population mismatch')
        for label in ('Modified', 'Unmodified'):
            if (integer(row[label]) != integer(stats['counts_' + label.lower()][name])
                    or integer(row[label]) != native[name, label.upper()]):
                raise ValueError('Native window counts disagree with allele table')
        if integer(row['Modified']) + integer(row['Unmodified']) != totals[name]:
            raise ValueError('Native modification counts do not reconcile')
        per_ref[name] = dict(**_summarize(counts[name]), ordinary_alignments=totals[name],
                             native_window_modified=integer(row['Modified']),
                             fixed_alignment_counts={s: counts[name]['fixed_' + s] for s in STATES})
    combined = _summarize(sum(counts.values(), Counter()))
    return dict(method='intended_sites_from_crispresso_alleles', version=VERSION,
                status='REPORTABLE' if any(combined[k]['denominator'] for k in ('site_A','site_B')) else 'NOT_ASSESSABLE',
                input_pairs=raw, preprocessed=merged, aligned=aligned, preprocessing_loss=raw-merged,
                unaligned=merged-aligned, ambiguous=partition['ambiguous_aligned_reads'],
                discarded=partition['discarded_aligned_reads'], combined=combined, backend_reference=per_ref,
                copy_assignment='Core alignment reference only; biological attribution requires independent diagnostics.',
                windows=windows)


def run_core_sites(*, targets, r1, r2, input_pairs, core, runtime_digest, output, windows=None):
    """Run one guide-free multi-WT alignment in the supplied prepared mate order."""
    targets = tuple(targets)
    designs = _panel(targets)
    if integer(input_pairs) == 0:
        raise ValueError('EMPTY_INPUT')
    if core.version != VERSION or runtime_digest != IMAGE:
        raise UnqualifiedSiteBackend('UNQUALIFIED_BACKEND_RUNTIME', 'Expected the pinned CRISPResso2 2.3.4 runtime')
    explicit_override = windows is not None
    if windows is None:
        windows = {t.copy_name: getattr(t, 'quantification_window_coordinates', None) for t in targets}
        if any(windows[t.copy_name] in (None, '0') and any(getattr(t, field, None) is not None for field in
               ('quantification_window_size', 'quantification_window_center')) for t in targets):
            raise UnqualifiedSiteBackend('UNMAPPED_GUIDE_RELATIVE_WINDOW',
                                         'Guide-relative windows require explicit mapped coordinates in a guide-free run')
    if set(windows) != set(designs):
        raise ValueError('Provide one explicit window per reference')
    selections = [windows[name] for name in designs]
    if any(v is not None for v in selections) and any(v is None for v in selections):
        raise UnqualifiedSiteBackend('INCOMPLETE_SITE_WINDOWS', 'Missing window for a subset of the panel')
    for key, value in windows.items():
        if value not in (None, '0'):
            _ranges(value, len(designs[key][0]))
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.' + output.name + '.incomplete-', dir=output.parent))
    try:
        hashes, names = [], []
        for mate, source in enumerate((Path(r1), Path(r2)), 1):
            with source.open('rb') as handle:
                gzipped = handle.read(2) == b'\x1f\x8b'
            name = f'input_R{mate}.fastq' + ('.gz' if gzipped else '')
            before = sha256_file(source)
            shutil.copyfile(source, stage / name)
            if sha256_file(stage / name) != before:
                raise ValueError('Prepared input changed during staging')
            names.append(name)
            hashes.append(before)
        argv = [core.path, '--fastq_r1', names[0], '--fastq_r2', names[1],
                '--amplicon_seq', ','.join(t.wt_sequence for t in targets),
                '--amplicon_name', ','.join(designs), '--name', 'sites', '--write_detailed_allele_table',
                '--keep_intermediate', '--suppress_report', '--suppress_plots']
        if any(selections):
            argv.extend(['--quantification_window_coordinates', ','.join(selections)])
        start = utc_now()
        with (stage / 'core.log').open('w') as log:
            proc = subprocess.run(argv, cwd=stage, stdout=log, stderr=subprocess.STDOUT)
        if proc.returncode:
            raise BackendError('COMMAND_FAILED', (stage / 'core.log').read_text()[-2000:])
        child = stage / 'CRISPResso_on_sites'
        report = read_core_sites(child, targets, expected_input_pairs=input_pairs)
        args = read_json(child / 'CRISPResso2_info.json')['running_info']['args']['value']
        if [args['fastq_r1'], args['fastq_r2']] != names or (any(selections) and
                args['quantification_window_coordinates'] != ','.join(selections)):
            raise ValueError('Backend input or requested coordinates mismatch')
        report['execution'] = dict(argv=argv, version_probe=core.probe, runtime_digest=runtime_digest,
                                   input_sha256=hashes, started_at=start, ended_at=utc_now(),
                                   return_code=proc.returncode, native_directory='CRISPResso_on_sites',
                                   window_selection='caller_override' if explicit_override else 'target_or_backend_default')
        (stage / 'aligned_site_counts.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
        if output.exists() or output.is_symlink():
            raise FileExistsError(output)
        stage.rename(output)
        return report
    finally:
        if stage.exists():
            shutil.rmtree(stage)
