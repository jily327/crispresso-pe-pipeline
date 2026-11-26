"""Matched-reference controls for copy-conditioned measurements at observed mate lengths."""
from collections import Counter

from peanalyzer.fastq import FastqRecord
from peanalyzer.observability import physical_forward_mate
from peanalyzer.schemas import reverse_complement

SELECTIVE = 'EDIT_STATE_SELECTIVE_COPY_ROUTING'
CROSS_COPY = 'CROSS_COPY_ROUTING_IN_MATCHED_GEOMETRY'


def observed_pair_geometry(pair, targets):
    return (len(pair[0].sequence), len(pair[1].sequence), physical_forward_mate(pair, targets) or 0)


def _states(target, geometry):
    states = {'WT':target.wt_sequence, 'PE':target.prime_edited_sequence}
    source = geometry['copies'][target.copy_name].get('native_reference', {}).get('extension_match', {})
    if source.get('status') == 'copy_polymorphism':
        converted = list(target.prime_edited_sequence)
        for site in source['mismatches']:
            converted[site['original_pe_position']] = site['expected']
        states['PE_SNP_converted'] = ''.join(converted)
    return states


def matched_pair(sequence, lengths, forward):
    # A simulated control contains the biological reference up to the measured
    # mate length. Bases beyond a molecular end cannot supply copy evidence.
    reads = [sequence[:n] if mate == forward else reverse_complement(sequence[-n:])
             for mate, n in enumerate(lengths, 1)]
    return tuple(FastqRecord(f'@matched/{m}\n'.encode(),(seq+'\n').encode(),b'+\n',('I'*len(seq)+'\n').encode())
                 for m, seq in enumerate(reads, 1))


def copy_routing_eligibility(geometries: Counter, targets, geometry, policy, *, legacy=False):
    """Apply the actual router to WT and PE controls matched to each observed geometry.

    A failure invalidates the producing copy and any recipient of a cross-route.
    Physical assignments, including true zeros in the routing ledger, remain QC.
    """
    from peanalyzer.routing import route_pair
    reasons = {t.copy_name:set() for t in targets}
    trials = []
    for (r1, r2, observed_forward), count in sorted(geometries.items()):
        for forward in ((observed_forward,) if observed_forward else (1, 2)):
            for t in sorted(targets,key=lambda t:t.copy_name):
                outcomes = {}
                for state, seq in _states(t, geometry).items():
                    pair = matched_pair(seq, (r1,r2), forward)
                    row = route_pair(pair,targets,geometry,policy,legacy=legacy)
                    outcomes[state] = dict(assigned_copy=row['assigned_copy'],category=row['category'])
                calls = {outcome['assigned_copy'] for outcome in outcomes.values()}
                if len(calls) > 1:
                    reasons[t.copy_name].add(SELECTIVE)
                for recipient in calls - {None,t.copy_name}:
                    reasons[t.copy_name].add(CROSS_COPY)
                    reasons[recipient].add(CROSS_COPY)
                trials.append(dict(source_copy=t.copy_name, r1_length=r1, r2_length=r2,
                                   observed_forward_mate=observed_forward or None, control_forward_mate=forward,
                                   observed_pairs=count, states=outcomes))
    for copy in reasons:
        controls = [t for t in trials if t['source_copy'] == copy]
        if controls and not any(all(s['assigned_copy'] == copy for s in t['states'].values()) for t in controls):
            if not reasons[copy]:
                reasons[copy].add('NO_MATCHED_STATE_ROUTING_SUPPORT')
    return dict(contract='matched-amplicon-ends-at-observed-physical-mate-lengths-v1',
                observed_pairs=sum(geometries.values()),trials=trials,
                reason_codes={copy:sorted(values) for copy,values in sorted(reasons.items())})
