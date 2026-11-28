"""Independent sample 1A acquisition-order control and integer recount (no production parser)."""
import csv
import io
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'epsps-real'))
from audit import calls, haplotypes, rc, validate_sources
from peanalyzer.fastq import paired_fastq, read_fastq, read_id


def recount(inputs, work, executable):
    work.mkdir(parents=True)
    paths, panels = validate_sources(inputs)
    refs = panels['EPSPS_284bp']
    fwd, rev = calls()
    ids = set()
    # Recover 1A directly from original raw mates, preserving acquisition order.
    with (work/'R1.fastq').open('xb') as left, (work/'R2.fastq').open('xb') as right:
        for one, two in paired_fastq(paths['EPSPS_1106_R1.fastq.gz'], paths['EPSPS_1106_R2.fastq.gz']):
            if (fwd.get(one.sequence[:9].decode()), rev.get(two.sequence[:9].decode())) != ('1','A'):
                continue
            ident = read_id(one, 1)
            assert ident not in ids
            ids.add(ident)
            for mate, (rec, trim, out) in enumerate(((one,26,left), (two,27,right)), 1):
                rec = rec.trimmed(trim)
                out.write(b'@'+ident+b'/'+str(mate).encode()+b'\n'+rec.sequence+b'\n+\n'+rec.quality_line)
    argv = [executable, '-r1','R1.fastq','-r2','R2.fastq', '-a', ','.join(refs[n]['wt_sequence'] for n in refs),
            '-an', ','.join(refs), '--name','direct', '--quantification_window_coordinates',
            '146-146_157-157,146-146_157-157', '--keep_intermediate', '--write_detailed_allele_table',
            '--suppress_report','--suppress_plots']
    with (work/'direct.log').open('w') as log:
        subprocess.run(argv, cwd=work, stdout=log, stderr=subprocess.STDOUT, check=True)
    root = work/'CRISPResso_on_direct'
    info = json.loads((root/'CRISPResso2_info.json').read_text())
    assert info['running_info']['version'] == '2.3.4'
    for name, ref in refs.items():
        backend = info['results']['refs'][name]
        assert backend['sequence'] == ref['wt_sequence'] and backend['include_idxs']['value'] == [146,157]
    template = haplotypes(refs)
    aligned_sequences, calls_by_ref, exact, symbols = Counter(), Counter(), Counter(), Counter()
    ambiguous = 0
    with ZipFile(root/'Alleles_frequency_table.zip') as archive:
        with archive.open('Alleles_frequency_table.txt') as handle:
            for row in csv.DictReader(io.TextIOWrapper(handle), delimiter='\t'):
                seq, name, n = row['Aligned_Sequence'], row['Reference_Name'], int(row['#Reads'])
                literal = seq.replace('-', '')
                key = min(literal, rc(literal))
                assert key not in aligned_sequences
                aligned_sequences[key] = n
                if name.startswith('AMBIGUOUS_'):
                    ambiguous += n
                    continue
                assert name in refs
                backbone = row['Reference_Sequence']
                assert backbone.replace('-', '') == refs[name]['wt_sequence']
                bases = ''.join(q for r,q in zip(backbone,seq,strict=True) if r != '-')
                pair = bases[146] + bases[157]
                state = {'GG':'WT','AG':'A_only','GA':'B_only','AA':'AB'}.get(pair,'other')
                calls_by_ref[name,state] += n
                symbols[name,146,bases[146]] += n
                symbols[name,157,bases[157]] += n
                if literal in template:
                    exact[template[literal]] += n
    replay, seen_ids, all_merged = Counter(), set(), Counter()
    for rec in read_fastq(root/'out.extendedFrags.fastq.gz'):
        ident = read_id(rec,1)
        assert ident in ids and ident not in seen_ids
        seen_ids.add(ident)
        dna = rec.sequence.decode()
        key = min(dna, rc(dna))
        if key in aligned_sequences:
            replay[key] += 1
        if dna in template or rc(dna) in template:
            all_merged[template.get(dna) or template[rc(dna)]] += 1
    assert replay == aligned_sequences and all_merged == exact
    def table(file):
        with (root/file).open() as stream:
            return list(csv.DictReader(stream,delimiter='\t'))
    mapping, = table('CRISPResso_mapping_statistics.txt')
    assert (len(ids),len(seen_ids),sum(replay.values())) == tuple(int(mapping[k]) for k in
                                         ('READS IN INPUTS','READS AFTER PREPROCESSING','READS ALIGNED'))
    assert sum(replay.values()) == ambiguous + sum(calls_by_ref.values())
    copies = {}
    for row in table('CRISPResso_quantification_of_editing_frequency.txt'):
        name = row['Amplicon']
        with (root/f'{name}.Quantification_window_nucleotide_frequency_table.txt').open() as stream:
            lines = csv.reader(stream,delimiter='\t')
            assert next(lines)[1:] == ['G','G']
            for symbol, a, b in lines:
                assert (float(a),float(b)) == (symbols[name,146,symbol], symbols[name,157,symbol])
        assert int(row['Reads_aligned']) == sum(v for (c,s),v in calls_by_ref.items() if c==name)
        copies[name] = dict(ordinary_alignments=int(row['Reads_aligned']), native_window_modified=int(row['Modified']),
                            aligned_site_bases={s:calls_by_ref[name,s] for s in ['WT','A_only','B_only','AB','other']},
                            literal_merged_templates={s:exact[name,s] for s in ['WT','A_only','B_only','AB']})
    return dict(raw_pairs=len(ids), merged=len(seen_ids), aligned=sum(replay.values()),
                unaligned_after_merge=len(seen_ids)-sum(replay.values()), ambiguous={'AMBIGUOUS':ambiguous},
                copies=copies, window_indices=[146,157])


if __name__ == '__main__':
    data = recount(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])
    print(json.dumps(data,indent=2,sort_keys=True))
