# Native PE strand and window verification

The four conventional PE runs used the same 350 artificial prepared pairs and Core 2.3.4 from the repository's pinned image. Both supplied reference orientations gave 120 native PE-reference assignments among 330 aligned reads. Comparing complete allele sequences with the copy1 definitions gave 60 exact PE and 80 exact WT reads. These are distinct measurement populations. The deposited summaries contain integer results and the effective windows. The scripts reproduce them in new directories, including all raw Core outputs.

```bash
python docs/validation/pe-normalization/reproduce.py /tmp/pe-parity-new /path/to/peanalyzer-crispresso
python docs/validation/pe-normalization/reproduce_extension.py /tmp/extension-parity-new /path/to/peanalyzer-crispresso
```

PEAnalyzer searches each supplied WT for the experimental spacer on both strands. One unique reverse site requires reverse-complementing both supplied reference sequences for the Core handoff. The experimental RNA inputs retain their supplied sequences. The complete genomic-oriented extension must occur exactly once in the intended product. An ambiguous spacer, ambiguous extension location or unsupported mismatch blocks native PE analysis for that copy. The execution manifest stores the supplied and backend WT and PE, the selected orientation and both explicit window definitions.

For a reverse copy, the backend base at index `p` corresponds to supplied base `L-1-p` using the length of the relevant WT or PE. The transform mirrors each inclusive explicit WT interval and its ends. Preflight estimates the union of applicable guide and flap windows. PEAnalyzer reads the effective Reference and Prime-edited positions from `results.refs.*.include_idxs` in the native child. Native Core uses guide-derived windows when the explicit-coordinate field is absent or equals `0`. The synthetic default WT window was 111–112 and 140–149. It excluded intended site 122. The explicit 120–124 window included the site. In the reverse representation these same explicit positions are 115–119 and include site 117. Window diagnostics do not alter the whole-product exact definition.

## Secondary-copy extension polymorphism

A unique alignment from a panel copy with an exact complete extension can identify mismatches on another copy. To identify a natural SNP, both copies must retain their respective base between their WT and intended references at that position. Each mismatch records its 0-based position on the supplied WT, supplied PE and experimental 5′-to-3′ extension. The extension alone does not identify an RTT/PBS boundary. Nonunique or gapped correspondence and inconsistent anchor evidence do not establish a secondary-copy polymorphism.

The routing gate excludes the template-variable site from copy-discriminating evidence. A separate conventional single-WT Core run consumes the verified confident cohort. Exact complete allele sequences from its ZIP distinguish WT, intended product with the copy variant retained, and intended product with all identified extension variants converted. Other complete modifications and unresolved fragments retain separate counts. Preprocessing and alignment losses enter unresolved. These PEAnalyzer-derived counts reconcile to the verified cohort input. The synthetic fixture produced 8 WT, 7 intended retained, 6 intended converted and 5 other among 26 assigned secondary-copy molecules. Two additional mosaics were quarantined. The primary native fraction was 4/7. Native PE remained blocked for the secondary copy.

This is synthetic qualification. The supplied files contain ALSW and EPSPS references and reads. Confirmation of the ALSP P193S case requires its original WT and intended references, sample data and execution metadata.
