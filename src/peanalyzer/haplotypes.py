"""Two-substitution amplicon measurements on verified demultiplexed read pairs."""
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import re

from peanalyzer.demux_verify import sha256_file, verify_demux_output
from peanalyzer.fastq import paired_fastq, read_id
from peanalyzer.geometry import aligner, columns
from peanalyzer.observability import BOUNDARY_REASONS, reconstruct_product, reference_observable
from peanalyzer.schemas import reverse_complement, sequence

STATES = ('WT', 'A_only', 'B_only', 'AB')
FLANK = 12
MARKER_LENGTH = 15
MIN_PHRED = 30


@dataclass
class Panel:
    name: str
    sites: dict
    templates: dict
    contexts: dict
    markers: list
    marker_starts: tuple
    single_contexts: dict
    sha256: str


def load_panel(path, marker_starts):
    """Read one panel, in the deposited panel|copy|WT/intended_PE|length=N FASTA layout."""
    data = path.read_bytes()
    panels, copies = set(), defaultdict(dict)
    fasta = data.decode('ascii').strip()
    if not fasta.startswith('>'):
        raise ValueError('Missing FASTA header')
    for record in fasta[1:].split('\n>'):
        if not record:
            continue
        header, *lines = record.splitlines()
        match = re.fullmatch(r'([\w.-]+)\|([\w.-]+)\|(WT|intended_PE)\|length=(\d+)', header)
        if not match or not lines:
            raise ValueError('Expected panel|copy|WT or intended_PE|length=N FASTA records')
        name, copy, state, length = match.groups()
        dna = sequence(''.join(lines))
        if len(dna) != int(length) or state in copies[copy]:
            raise ValueError(f'Duplicate reference or incorrect length for {header}')
        copies[copy][state] = dna
        panels.add(name)
    if len(panels) != 1:
        raise ValueError('Select exactly one reference panel')
    templates = {copy: {('PE' if state == 'intended_PE' else state): dna for state, dna in pair.items()}
                 for copy, pair in copies.items()}
    panel = build_panel(panels.pop(), templates, marker_starts)
    panel.sha256 = hashlib.sha256(data).hexdigest()
    return panel


def _candidate_markers(copies, sites, templates):
    """One disjoint invariant interval on either side, unique to each copy and strand."""
    if len(copies) < 2:
        return ()
    minimum_length = min(len(pair['WT']) for pair in copies.values())
    left, right = [], []
    for start in range(minimum_length - MARKER_LENGTH + 1):
        end = start + MARKER_LENGTH
        before = all(end <= a for a, _ in sites.values())
        after = all(start > b for _, b in sites.values())
        if not (before or after):
            continue
        motifs = {copy: pair['WT'][start:end] for copy, pair in copies.items()}
        if len(set(motifs.values())) != len(copies):
            continue
        if all(_unique_marker(template, motif, any(c == copy for c, _ in identities))
               for template, identities in templates.items() for copy, motif in motifs.items()):
            (left if before else right).append(start)
    return (left[-1], right[0]) if left and right else ()


def _unique_marker(template, motif, expected):
    first = template.find(motif)
    return ((first >= 0) == expected and template.find(motif, first+1) < 0
            and reverse_complement(motif) not in template)


def build_panel(name, copies, marker_starts=None):
    """Build only locally homologous two-substitution designs on the supplied strand."""
    if not copies:
        raise ValueError('Missing target reference copies')
    if marker_starts and (len(marker_starts) < 2 or min(marker_starts) < 0 or
                          any(b-a < MARKER_LENGTH for a,b in zip(sorted(marker_starts), sorted(marker_starts)[1:]))):
        raise ValueError('Copy calls require at least two disjoint 15-base marker intervals')
    sites, contexts, templates = {}, {}, defaultdict(list)
    single_contexts = {'A': {}, 'B': {}}
    for copy, pair in copies.items():
        if set(pair) != {'WT', 'PE'}:
            raise ValueError(f'Missing WT or intended_PE for {copy}')
        wt, pe = sequence(pair['WT']), sequence(pair['PE'])
        edits = [i for i, (x, y) in enumerate(zip(wt, pe)) if x != y]
        if len(wt) != len(pe) or len(edits) != 2:
            raise ValueError(f'{copy} must have exactly two intended substitutions')
        placements = aligner().align(wt, pe)
        if len(placements) != 1 or any(i != j for i, j in columns(placements[0])):
            raise ValueError(f'{copy} has competing intended substitution/indel placements')
        a, b = edits
        if a < FLANK or b + FLANK >= len(wt):
            raise ValueError(f'Both intended sites need {FLANK} flanking bases')
        sites[copy] = edits
        for state in STATES:
            allele = list(wt)
            if state in ('A_only', 'AB'):
                allele[a] = pe[a]
            if state in ('B_only', 'AB'):
                allele[b] = pe[b]
            template = ''.join(allele)
            templates[template].append((copy, state))
            motif = template[a-FLANK:b+FLANK+1]
            if state in contexts and contexts[state] != motif:
                raise ValueError('Intended sites need matching local context across copies')
            contexts[state] = motif
            for label, pos in (('A', a), ('B', b)):
                flank = template[pos-FLANK:pos+FLANK+1]
                single_contexts[label][flank] = template[pos] == pe[pos]
    if marker_starts is None:
        marker_starts = _candidate_markers(copies, sites, templates)
    markers = [{} for _ in marker_starts]
    for copy, pair in copies.items():
        wt, edits = pair['WT'], sites[copy]
        for start, region in zip(marker_starts, markers):
            end = start + MARKER_LENGTH
            if end > len(wt) or any(start <= edit < end for edit in edits):
                raise ValueError(f'Copy marker at {start} outside reference or contains an edit')
            region[copy] = wt[start:end]
    if any(len(set(region.values())) != len(copies) for region in markers):
        raise ValueError('Each marker must uniquely distinguish the reference copies')
    if markers and any(not (min(marker_starts) + MARKER_LENGTH <= a and max(marker_starts) > b)
                       for a, b in sites.values()):
        raise ValueError('Require edit-independent markers on both sides of the intended sites')
    for template, identities in templates.items():
        states = {s for _, s in identities}
        if len(states) != 1:
            raise ValueError('Contradictory full-template states in reference panel')
        for state, motif in contexts.items():
            first = template.find(motif)
            if ((first >= 0) != (state in states) or template.find(motif, first+1) >= 0 or
                    reverse_complement(motif) in template):
                raise ValueError('Site context has ambiguous position or strand in this panel')
        for region in markers:
            for copy, motif in region.items():
                expected = any(c == copy for c, _ in identities)
                first = template.find(motif)
                if ((first >= 0) != expected or template.find(motif, first+1) >= 0 or
                        reverse_complement(motif) in template):
                    raise ValueError('Copy marker must uniquely distinguish copies and strands')
    # A unique joint anchor can still contain a repeated single-site anchor.
    # Quarantine that marginal assay while retaining the observable joint measurement.
    for label, motifs in single_contexts.items():
        site_index = 0 if label == 'A' else 1
        for template, identities in templates.items():
            expected_pos = sites[identities[0][0]][site_index] - FLANK
            if any((template.find(motif) not in (-1, expected_pos)
                    or template.find(motif, expected_pos + 1) >= 0 or reverse_complement(motif) in template)
                   for motif in motifs):
                single_contexts[label] = {}
                break
    identity = hashlib.sha256(json.dumps(copies, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return Panel(name, sites, dict(templates), contexts, markers, tuple(marker_starts), single_contexts, identity)


def mate_call(dna, quality, panel):
    hits = []
    for state, motif in panel.contexts.items():
        start = dna.find(motif)
        if start >= 0:
            if dna.find(motif, start+1) >= 0:
                return None, 'context'
            q = min(quality[start+FLANK], quality[start+len(motif)-FLANK-1])
            hits.append((state, q))
    if len(hits) != 1:
        return None, 'context'
    state, quality = hits[0]
    return (state, None) if quality >= 33 + MIN_PHRED else (None, 'low_quality')


def marker_copy(mates, panel):
    if len(panel.sites) == 1:
        return next(iter(panel.sites))
    votes = set()
    for region in panel.markers:
        for read in mates:
            hits = []
            for copy, motif in region.items():
                pos = read.find(motif)
                if pos >= 0:
                    if read.find(motif, pos+1) >= 0:
                        return None
                    hits.append(copy)
            if len(hits) != 1:
                return None
            votes.update(hits)
    return next(iter(votes)) if len(votes) == 1 else None


def full_call(left, right, panel, boundary_reasons=None):
    references = tuple(panel.templates)
    # A necessary end-match check avoids reconstructing both orientations for
    # unobserved products. Final admission uses the shared exact overlap policy.
    if not any(ref.startswith(left[:len(ref)]) and ref.endswith(right[-len(ref):]) for ref in references):
        return None
    product, reason = reconstruct_product(left, right, references)
    if boundary_reasons is not None and reason in BOUNDARY_REASONS:
        boundary_reasons.add(reason)
    if reason or product not in panel.templates:
        return None
    if not all(reference_observable(ref, len(left), len(right)) for ref in references):
        return None
    assignments = panel.templates[product]
    copy, state = assignments[0]
    return state, copy if len(assignments) == 1 else None


def fraction(n, d):
    return dict(numerator=n, denominator=d, fraction=n/d if d else None)


def counts_report(counts):
    values = {s: counts[s] for s in STATES}
    a, b, ab = values['A_only'], values['B_only'], values['AB']
    total = sum(values.values())
    return dict(counts=values, assessable=total, site_A=fraction(a+ab, total),
                site_B=fraction(b+ab, total), A_only=fraction(a,total), B_only=fraction(b,total),
                double_edit=fraction(ab,total), any_edit=fraction(a+b+ab,total))


def summarize_calls(counts, panel):
    grouped = {c: Counter({s: counts[c, s] for s in STATES}) for c in [*panel.sites, None]}
    combined = counts_report(sum(grouped.values(), Counter()))
    return dict(combined=combined, copies={c: counts_report(grouped[c]) for c in panel.sites},
                unresolved_copy=counts_report(grouped[None]))


def single_site_call(read, qualities, motifs):
    hits = []
    for motif, edited in motifs.items():
        pos = read.find(motif)
        if pos >= 0:
            if read.find(motif, pos + 1) >= 0:
                return None
            hits.append((edited, qualities[pos + FLANK]))
    if len(hits) == 1 and hits[0][1] >= 33 + MIN_PHRED:
        return hits[0][0]
    return None


def _set_marginals(report, marginal, panel):
    for site in ('A', 'B'):
        for copy in (*panel.sites, None):
            group = report['unresolved_copy'] if copy is None else report['copies'][copy]
            wt, edit = marginal[site, copy, False], marginal[site, copy, True]
            group['site_' + site] = fraction(edit, wt + edit)
        total_edit = sum(count for (label, _, edit), count in marginal.items() if label == site and edit)
        total = sum(count for (label, _, _), count in marginal.items() if label == site)
        report['combined']['site_' + site] = fraction(total_edit, total)


def measure_sample(sample, panel, trims, is_control):
    joint, exact, qc, orientation = Counter(), Counter(), Counter(), Counter()
    rejected_boundaries = Counter()
    seen, marginal = set(), Counter()
    for pair in paired_fastq(sample.r1, sample.r2):
        ident = read_id(pair[0], 1)
        if ident in seen:
            raise ValueError(f'Duplicate read pair in {sample.sample_id}')
        seen.add(ident)
        if any(len(rec.sequence) <= trim for rec, trim in zip(pair, trims)):
            qc['too_short'] += 1
            continue
        reads = [rec.sequence[trim:].decode().upper() for rec, trim in zip(pair, trims)]
        scores = [rec.quality_line[trim:].rstrip() for rec, trim in zip(pair, trims)]
        full_hits, site_hits, failures = [], [], set()
        boundary_reasons = set()
        single_hits = {'A': [], 'B': []}
        for f, r in ((0, 1), (1, 0)):
            left, right = reads[f], reverse_complement(reads[r])
            full = full_call(left, right, panel, boundary_reasons)
            if full:
                full_hits.append(full)
            for site, motifs in panel.single_contexts.items():
                call1 = single_site_call(left, scores[f], motifs)
                call2 = single_site_call(right, scores[r][::-1], motifs)
                if call1 is not None and call1 == call2:
                    single_hits[site].append((marker_copy((left, right), panel), call1))
            first, second = mate_call(left, scores[f], panel), mate_call(right, scores[r][::-1], panel)
            if 'context' in (first[1], second[1]):
                continue
            if 'low_quality' in (first[1], second[1]):
                failures.add('low_quality')
            elif first[0] != second[0]:
                failures.add('discordant')
            else:
                site_hits.append((first[0], marker_copy((left, right), panel), f))
        for site, hits in single_hits.items():
            if len(hits) == 1:
                copy, edited = hits[0]
                marginal[site, copy, edited] += 1
        if boundary_reasons:
            rejected_boundaries.update(boundary_reasons)
        elif len(full_hits) == 1:
            state, copy = full_hits[0]
            exact[copy, state] += 1
        if len(site_hits) == 1 and not failures:
            state, copy, forward_mate = site_hits[0]
            joint[copy, state] += 1
            orientation[f'R{forward_mate+1}_forward'] += 1
        elif len(site_hits) > 1 or (site_hits and failures):
            qc['ambiguous_orientation'] += 1
        else:
            qc['low_quality' if 'low_quality' in failures else
               'discordant' if 'discordant' in failures else 'missing_or_nonunique_context'] += 1
    if len(seen) != sample.pairs or sum(qc.values()) + sum(joint.values()) != sample.pairs:
        raise ValueError(f'Pair reconciliation failed for {sample.sample_id}')
    if sha256_file(sample.r1) != sample.r1_sha256 or sha256_file(sample.r2) != sample.r2_sha256:
        raise ValueError(f'Demultiplexed reads changed for {sample.sample_id}')
    full = summarize_calls(exact, panel)
    joint_report = summarize_calls(joint, panel)
    _set_marginals(joint_report, marginal, panel)
    if not sample.pairs:
        status = 'EMPTY_NEGATIVE_CONTROL' if is_control else 'EMPTY_SAMPLE'
    else:
        status = 'ASSESSED' if joint else 'NO_CALLABLE_SITE_PAIRS'
    return dict(status=status, declared_negative_control=is_control, input_pairs=sample.pairs,
                two_site_q30=joint_report, site_exclusions=dict(qc), site_orientation=dict(orientation),
                full_templates=full, full_template_boundary_reasons=dict(rejected_boundaries), full_template_exclusions=sample.pairs-full['combined']['assessable'],
                exact_double_edit_fraction=dict(numerator=None, denominator=None, fraction=None,
                    status='NOT_ASSESSABLE', reason_codes=['CANONICAL_M4_RESULT_REQUIRED']))


def measure_haplotypes(demux_root, references, trims, marker_starts, negative_controls):
    if min(trims) < 0:
        raise ValueError('Analysis trim lengths must be nonnegative')
    panel = load_panel(references, marker_starts)
    archive = verify_demux_output(demux_root)
    negative_controls = set(negative_controls) | {row['barcode_id'] for row in archive.summary['samples']
                                                if row.get('sample_role') == 'negative_control'}
    unknown = negative_controls - {s.sample_id for s in archive.samples}
    if unknown:
        raise ValueError(f'Unknown negative-control barcode IDs: {sorted(unknown)}')
    samples = {s.sample_id: measure_sample(s, panel, trims, s.sample_id in negative_controls)
               for s in archive.samples}
    if sha256_file(archive.root / '01_demux_QC/demux_summary.json') != archive.summary_sha256:
        raise ValueError('Demux summary changed during analysis')
    return dict(contract='two-site-haplotypes-v1', measurement='paired_reads', panel=panel.name,
                reference_fasta_sha256=panel.sha256, demux_summary_sha256=archive.summary_sha256,
                site_coordinates_0based=panel.sites, analysis_trim_5p=list(trims),
                site_flank_length=FLANK, site_min_phred=MIN_PHRED, copy_marker_starts_0based=list(panel.marker_starts),
                copy_marker_length=MARKER_LENGTH, samples=samples)
