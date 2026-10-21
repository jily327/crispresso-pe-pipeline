"""Reference geometry, using Biopython alignments rather than positional guesses."""

from itertools import combinations

from Bio.Align import PairwiseAligner
from Bio.Seq import Seq

from peanalyzer.schemas import Target, reverse_complement


def aligner(*, reads=False):
    engine = PairwiseAligner(mode='global', match_score=2, mismatch_score=-3,
                            open_gap_score=-6, extend_gap_score=-1)
    if reads:
        engine.query_left_gap_score = engine.query_right_gap_score = 0
    return engine


def columns(alignment):
    """Aligned coordinate pairs; None denotes a gap (no fabricated base index)."""
    coords = alignment.coordinates
    result = []
    for i in range(coords.shape[1]-1):
        a, b = map(int, coords[:, i]); c, d = map(int, coords[:, i+1])
        if c > a and d > b:
            result.extend(zip(range(a, c), range(b, d)))
        elif c > a:
            result.extend((p, None) for p in range(a, c))
        else:
            result.extend((None, p) for p in range(b, d))
    return result


def geometry(targets: list[Target], *, coding: dict | None = None, primers: dict | None = None) -> dict:
    if not targets or len({t.target_name for t in targets}) != 1:
        raise ValueError('geometry requires one biological target at a time')
    targets = sorted(targets, key=lambda t:t.copy_name)
    if len({t.copy_name.casefold() for t in targets}) != len(targets):
        raise ValueError('duplicate copy identity')
    fields = ('pegRNA_spacer', 'pegRNA_extension', 'nicking_guide', 'pegRNA_scaffold')
    if any(len({getattr(t, f) for t in targets}) != 1 for f in fields):
        raise ValueError('one target must retain one shared experimental guide/extension/nick/scaffold')
    reasons, pairwise, events, maps = [], [], {}, {}
    def reason(code, severity='WARN', **context):
        reasons.append(dict(code=code, severity=severity, **context))
    anchor = targets[0].wt_sequence
    engine = aligner()
    for target in targets:
        for state, seq in (('WT', target.wt_sequence), ('PE', target.prime_edited_sequence)):
            matches = engine.align(anchor, seq)
            if len(matches) != 1:
                reason('NONUNIQUE_REFERENCE_ALIGNMENT', 'BLOCKED', copy=target.copy_name, state=state)
            maps[target.copy_name, state] = columns(matches[0])
    for left, right in combinations(targets, 2):
        matches = engine.align(left.wt_sequence, right.wt_sequence)
        cols = columns(matches[0])
        differences = [dict(left_position=a, right_position=b,
                            left_allele=left.wt_sequence[a] if a is not None else '-',
                            right_allele=right.wt_sequence[b] if b is not None else '-')
                       for a,b in cols if a is None or b is None or left.wt_sequence[a] != right.wt_sequence[b]]
        pairwise.append(dict(copies=[left.copy_name, right.copy_name], differences=differences, count=len(differences),
                             alignment_coordinates=matches[0].coordinates.tolist()))
        if not differences:
            reason('INDISTINGUISHABLE_COPIES', 'BLOCKED', copies=[left.copy_name, right.copy_name])
        if any(a is None or b is None for a,b in cols):
            reason('COPY_INDEL_ROUTING_UNQUALIFIED', 'BLOCKED', copies=[left.copy_name, right.copy_name])
    diagnostics = []
    for pos in range(len(anchor)):
        alleles, positions, edited = {}, {}, False
        for target in targets:
            wtmap = dict(maps[target.copy_name, 'WT'])
            pemap = dict(maps[target.copy_name, 'PE'])
            w, p = wtmap.get(pos), pemap.get(pos)
            positions[target.copy_name] = w
            alleles[target.copy_name] = target.wt_sequence[w] if w is not None else '-'
            edited |= p is None or target.prime_edited_sequence[p] != alleles[target.copy_name]
        if len(set(alleles.values())) > 1:
            diagnostics.append(dict(position=pos, positions=positions, alleles=alleles, overlaps_edit=edited,
                                    usable_for_routing=not edited and '-' not in alleles.values()))
    copies = {}
    for target in targets:
        matches = engine.align(target.wt_sequence, target.prime_edited_sequence)
        if len(matches) != 1:
            reason('NONUNIQUE_EDIT_ALIGNMENT', 'BLOCKED', copy=target.copy_name)
        edits = []
        preceding_wt=-1
        for a,b in columns(matches[0]):
            old = target.wt_sequence[a] if a is not None else '-'
            new = target.prime_edited_sequence[b] if b is not None else '-'
            if old != new:
                edit=dict(wt_position=a, pe_position=b, old=old, new=new,
                          kind='insertion' if a is None else 'deletion' if b is None else 'substitution')
                if a is None: edit['wt_boundary']=preceding_wt+1
                edits.append(edit)
            if a is not None: preceding_wt=a
        events[target.copy_name] = edits
        guide = target.pegRNA_spacer
        forward = [i for i in range(len(target.wt_sequence)) if target.wt_sequence.startswith(guide, i)]
        reverse = [i for i in range(len(target.wt_sequence)) if target.wt_sequence.startswith(reverse_complement(guide), i)]
        if not forward and not reverse:
            reason('PE_GUIDE_REFERENCE_MISMATCH_UNSUPPORTED', 'BLOCKED', copy=target.copy_name)
        if not forward and reverse:
            reason('PE_GUIDE_ORIENTATION_UNSUPPORTED', 'BLOCKED', copy=target.copy_name)
        if len(forward)+len(reverse)>1:
            reason('NONUNIQUE_SPACER_LOCATION', 'BLOCKED', copy=target.copy_name)
        window = set()
        if target.quantification_window_coordinates and target.quantification_window_coordinates != '0':
            for interval in target.quantification_window_coordinates.split('_'):
                start,end = map(int,interval.split('-')); window.update(range(start,end+1))
        elif target.quantification_window_coordinates != '0':
            size = 1 if target.quantification_window_size is None else target.quantification_window_size
            center = -3 if target.quantification_window_center is None else target.quantification_window_center
            for start in forward:
                cut = start+len(guide)-1+center; window.update(range(cut-size+1,cut+size+1))
            for start in reverse:
                cut = start-center-1; window.update(range(cut-size+1,cut+size+1))
            extension=reverse_complement(target.pegRNA_extension)
            locations=[i for i in range(len(target.prime_edited_sequence)) if target.prime_edited_sequence.startswith(extension,i)]
            if len(locations)!=1:
                reason('PE_EXTENSION_LOCATION_UNSUPPORTED','BLOCKED',copy=target.copy_name)
            else:
                # 2.3.4 default: 5 bases each side of the extension flap boundary.
                pe_to_wt={b:a for a,b in columns(matches[0]) if b is not None}
                cut=locations[0]+len(extension)-1
                for p in range(cut-4,cut+6):
                    if pe_to_wt.get(p) is not None: window.add(pe_to_wt[p])
            if target.nicking_guide:
                for guide_seq,is_reverse in ((target.nicking_guide,False),(reverse_complement(target.nicking_guide),True)):
                    for start in range(len(target.wt_sequence)):
                        if target.wt_sequence.startswith(guide_seq,start):
                            cut=start-center-1 if is_reverse else start+len(guide_seq)-1+center
                            window.update(range(cut-size+1,cut+size+1))
        else:
            reason('QUANTIFICATION_WINDOW_DISABLED_CONFIRM_BACKEND',copy=target.copy_name)
            window=set(range(len(target.wt_sequence)))
        inside = [d['position'] for d in diagnostics if d['positions'][target.copy_name] in window]
        if inside: reason('DIAGNOSTIC_IN_QUANTIFICATION_WINDOW', copy=target.copy_name, positions=inside)
        distances = {str(d['position']):[abs(d['positions'][target.copy_name]-(e['wt_position'] if e['wt_position'] is not None else e['wt_boundary']))
                     if d['positions'][target.copy_name] is not None else None for e in edits] for d in diagnostics}
        copies[target.copy_name] = dict(edits=edits, diagnostic_to_edit_distances=distances,
            spacer_forward_starts=forward, spacer_reverse_starts=reverse,
            diagnostics_inside_spacer=[d['position'] for d in diagnostics if d['positions'][target.copy_name] is not None and any(s<=d['positions'][target.copy_name]<s+len(guide) for s in forward+reverse)],
            diagnostic_positions_in_quantification_window=inside)
        copies[target.copy_name]['quantification_window_positions']=sorted(p for p in window if 0<=p<len(target.wt_sequence))
        copies[target.copy_name]['quantification_window_scope']='preflight estimate for pinned defaults; confirm child Reference.include_idxs after backend end exclusions'
        if coding and target.copy_name in coding:
            offset = coding[target.copy_name]
            if type(offset) is not int or not 0<=offset<=2:
                raise ValueError('coding offset must be validated integer 0..2 on reference forward strand')
            annotations=[]
            for edit in edits:
                p=edit['wt_position']
                if edit['kind']!='substitution' or p is None or p<offset or len(target.wt_sequence)!=len(target.prime_edited_sequence):
                    annotations.append({'classification':'not_assessable'}); continue
                start=offset+((p-offset)//3)*3
                wt=target.wt_sequence[start:start+3]; pe=target.prime_edited_sequence[start:start+3]
                if len(wt)!=3: annotations.append({'classification':'partial_codon'}); continue
                annotations.append(dict(wt_codon=wt,pe_codon=pe,wt_aa=str(Seq(wt).translate()),pe_aa=str(Seq(pe).translate())))
            copies[target.copy_name]['coding_edits']=annotations
            diagnostic_coding=[]
            for other in targets:
                if other.copy_name==target.copy_name or other.copy_name not in coding: continue
                for d in diagnostics:
                    p=d['positions'][target.copy_name]; q=d['positions'][other.copy_name]
                    other_offset=coding[other.copy_name]
                    if type(other_offset) is not int or not 0<=other_offset<=2: raise ValueError('invalid coding offset')
                    if p is None or q is None or p<offset or q<other_offset: continue
                    a=offset+((p-offset)//3)*3; b=other_offset+((q-other_offset)//3)*3
                    codon1=target.wt_sequence[a:a+3];codon2=other.wt_sequence[b:b+3]
                    if len(codon1)!=3 or len(codon2)!=3: continue
                    aa1=str(Seq(codon1).translate());aa2=str(Seq(codon2).translate())
                    diagnostic_coding.append(dict(position=d['position'],other_copy=other.copy_name,codons=[codon1,codon2],amino_acids=[aa1,aa2],classification='synonymous' if aa1==aa2 else 'nonsynonymous'))
            copies[target.copy_name]['coding_diagnostics']=diagnostic_coding
        similarities=[]
        for other in targets:
            if other.copy_name==target.copy_name: continue
            differences=[]
            for sequence in (target.wt_sequence,target.prime_edited_sequence):
                cols=columns(engine.align(sequence,other.wt_sequence)[0])
                differences.append(sum(a is None or b is None or sequence[a]!=other.wt_sequence[b] for a,b in cols))
            similarities.append(dict(other_copy=other.copy_name,WT_difference_bases=differences[0],PE_difference_bases=differences[1],editing_increases_similarity=differences[1]<differences[0]))
        copies[target.copy_name]['similarity_to_other_WT']=similarities
    if any(d['overlaps_edit'] for d in diagnostics): reason('EDIT_DEPENDENT_DIAGNOSTIC_LOSS')
    for pair in pairwise:
        left,right=pair['copies']
        pair['edit_independent_diagnostic_count']=sum(d['usable_for_routing'] and d['alleles'][left]!=d['alleles'][right] for d in diagnostics)
        if pair['edit_independent_diagnostic_count']==0:
            reason('NO_EDIT_INDEPENDENT_PAIR_DIAGNOSTICS','BLOCKED',copies=[left,right])
    if len(targets)>1 and not any(d['usable_for_routing'] for d in diagnostics):
        reason('NO_EDIT_INDEPENDENT_DIAGNOSTICS','BLOCKED')
    primer_report=[]
    for name,interval in (primers or {}).items():
        start,end=interval
        if type(start) is not int or type(end) is not int or not 0<=start<end<=len(anchor):
            raise ValueError('invalid primer interval in anchor coordinates')
        sequences={t.copy_name:''.join(t.wt_sequence[b] if b is not None else '-' for a,b in maps[t.copy_name,'WT'] if a is not None and start<=a<end) for t in targets}
        primer_report.append(dict(name=name,interval=interval,sequences=sequences,copy_specific_pcr_may_be_feasible=len(set(sequences.values()))>1))
    return dict(schema_version=1,target_name=targets[0].target_name,coordinate_system='zero-based anchor WT; intervals half-open',
                anchor_copy=targets[0].copy_name,experimental_spacer=targets[0].pegRNA_spacer,
                status='BLOCKED' if any(r['severity']=='BLOCKED' for r in reasons) else 'WARN' if reasons else 'SAFE',
                reasons=reasons,pairwise=pairwise,diagnostics=diagnostics,copies=copies,primers=primer_report,
                haplotype_maps={f'{copy}:{state}':cols for (copy,state),cols in maps.items()})
