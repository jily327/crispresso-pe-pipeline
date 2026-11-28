# SCI-02 — Site calls disputed by equally scoring alignments

The audited candidate `2f567b88628eeb287bacc9febf3b65b3a00bfc7a` admitted all five ambiguous observations to its site A and joint denominators. The native detailed table has ten WT reads and a second allele with five reads, in which one A replaces the GG at reference positions 145–146. Deleting either G gives the same alignment score. The two explanations place a deletion or A at site A and agree on the intended A at site B. The native reference assignment and native modification counts are retained.

| Observation | Audited candidate | Corrected interpretation |
| --- | ---: | ---: |
| Site A edited / observable | 0 / 15 | 0 / 10 |
| Site B edited / observable | 5 / 15 | 5 / 15 |
| Jointly observable | 15 | 10 |
| Joint other/mixed | 5 | 0 |
| Joint unassessable | 0 | 5 |
| Disputed placement affecting A | Unavailable | 5 |

## Decision rule

The evidence is the genuine CRISPResso2 2.3.4 ordinary allele row for a specified WT reference. The native aligned query, native alignment choice, integer abundance and fixed-alignment site calls remain available. The supplementary method asks separately whether the observed nucleotide or internal deletion at each site is identifiable given the same sequence evidence.

For each site, a global affine-gap dynamic program tests the best possible competing placement that changes its call. The scoring contract for this conventional guide-free run is EDNAFULL and the backend's resolved opening/extension penalties, with zero position-specific incentives across that reference. The query may contain N. An exact repeated deletion with interchangeable bases is a fast sufficient ambiguity test. For other rows, a tagged reference coordinate either forbids alignment to the originally called nucleotide or requires pairing to a nucleotide when the native placement has a deletion. Native-column scoring uses the pinned Core terminal gap rule. Both the maximum-score candidate and any tie with the native row can invalidate the site. The dynamic program considers insertions, deletions and shifts over mismatches, across the whole sequence; it does not cap or sample traceback alternatives.

Biopython's global affine model can allow adjacent opposing gap runs that Core's three-state recurrence excludes. Its constrained optimum bounds Core's possible competitors from above. A competing upper-bound score as high as the native score causes withholding even if that alternate path would be unavailable to Core. The calculation also conservatively bounds whether an apparently internal deletion might instead lack end coverage. The original call is accepted only when alternatives score strictly below the native row. An unsupported substitution matrix or nonzero positional incentive withholds both site calls for that reference and records the reason. This is an eligibility decision for the supplementary site series; it does not modify a native allele or its count.

`qc.alternative_alignment_site_A` and `qc.alternative_alignment_site_B` count abundance whose site call failed this comparison, including any overlap. Unknown bases and absent coverage remain separately unassessable. Rows need both sites for joint haplotype fractions. A stable marginal call survives ambiguity at the other site. `qc.unqualified_alignment_scoring` counts abundance assessed with an unsupported scoring configuration.

The trusted workflow plan selects the original repeat-only algorithm when verifying a pre-remediation completed workspace. Historical files and stored site percentages are replayed under that contract. New reports use the corrected method.

## Checks and reproduction

The submitted audit's original SCI-02 native zip was reopened by importing `read_core_sites` from a clean `git archive 2f567b8 src`. The same native table was then read under the corrected source. The independent tests build explicit molecules with one-, two- and three-base gaps, both reported placements, both strands, unexpected site B bases and an insertion that admits two different mismatching bases at site A. A separate exhaustive small-string oracle enumerates independent alignment paths without calling PEAnalyzer or Biopython to generate truth. It checks every optimally supported site state for the designed strings. The 24 mismatch-shift regression cases fail on the frozen source and pass after correction.

To produce the EPSPS and known-truth evidence, use an editable installation and the pinned Docker image. Supply a directory with one copy of each of the five uploaded inputs. The native and direct output trees should remain available for audit. The script validates the compressed source hashes and deposited reference sequence identities, prepares each pair in the stated order with independent leading trim of 26/27, and invokes the same production multi-WT backend for four real populations and one synthetic population. For each managed run it replays the recorded command with the original Core binary in a separate Docker execution.

```sh
python docs/validation/remediation/sites/qualify_epsps.py /path/to/original-inputs /new/workdir --core peanalyzer-crispresso
python -m pytest -q tests/test_site_placement.py tests/test_backend_intended_sites.py
```

The real runs are conventional multi-WT alignment with explicit zero-based windows at 146 and 157 on each reference. Window-native modifications count Core events in those intervals. The experimental pegRNA, sample assignments and historical native PE settings require the original experimental metadata. Aligned site AB means the two intended bases were observed in the specified merged, ordinarily assigned population. It does not establish a whole-amplicon exact product, original molecule identity, or biological editing efficiency.

## Real populations and direct standalone parity

| Population | Input | Merged | Aligned | Ambiguous | A edited / observable | B edited / observable | Joint AB / observable | Native integer fields matched | Matching allele identities |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| SCI-02 | 15 | 15 | 15 | 0 | 0/10 | 5/15 | 0/10 | 77 | 2 |
| 1A acquired order | 5,564 | 5,465 | 5,040 | 1 | 52/5,039 | 29/5,039 | 21/5,039 | 80 | 727 |
| 1A forward mate first | 5,564 | 5,543 | 5,115 | 1 | 52/5,114 | 36/5,114 | 21/5,114 | 80 | 1,088 |
| All recognized, acquired order | 114,761 | 112,444 | 103,967 | 46 | 84/103,921 | 49/103,921 | 24/103,921 | 80 | 6,879 |
| All recognized, forward mate first | 114,761 | 114,250 | 105,769 | 49 | 115/105,720 | 186/105,718 | 25/105,718 | 80 | 12,553 |

All five native runs were individually replayed. For every run the managed and direct native values have zero integer differences, identical allele identities and abundance, matching ordered WT references and effective windows, and identical effective arguments. The direct process executed Core from the digest-pinned image without the PEAnalyzer wrapper. The 397 matched integer fields include Core mapping, per-reference quantification and JSON class counts. The supplementary A/B columns are a separate interpretation of those native alignments. The two site-specific placement QC counts were both zero in every real cohort. Two all-recognized, forward-first observations independently lack a site B base. The 1A observations are a subset of each corresponding all-recognized population.

Each record under [native-parity](native-parity) contains its full standalone command, prepared input hashes, managed and direct info hashes, exact runtime digest and per-metric integer comparison. The [preparation ledger](prepared.json) records the original compressed hashes and all physically observed barcode combinations. Run source hash: `640dad53e1b7fdc24c1b22cdd4fbcba5de624491a5eca2c1bdc772aea724a9b0`. The final distinction for legacy-workspace read-only verification was added after this execution snapshot. The production row interpreter on the integration branch was rerun against every preserved new native allele table after that change. [Frozen versus corrected counts](before-after.json)

## Development ledger

- A preliminary implementation applied the global decision even to tests of the old local repeat helper with short, non-native, end-sensitive alignments. Four tests failed. The repeat test now remains the original sufficient local check; every undecided site goes to the global score bound. All four original assertions pass. Their expectations were preserved.
- The first direct replay request used a path inside the managed cell. The direct-run validator rejected it. The qualification runner now uses a sibling directory. The next attempt detected a pre-existing exclusive reproduction script. The runner now verifies an existing manifest before reuse, preserving the populated cell and original failures.
- Historical verification initially compared new QC fields to historical stored tables and failed. The plan-bound historical recount recovered both completed workspaces in the earlier 40-pair `run` and `analyze` fixture; no historical report was rewritten.
- Two concurrent index operations returned a lock error, and simultaneous staging combined the SCI-02 implementation with SCI-03 in commit `c71f804`. The tracked site files and tests were checked against the working tree.

## Final installed package

The wheel built from `81c21c8b7dc536a6e2d1a22d446008407f625415` reread the five retained native outputs. Its complete JSON recount was byte-identical to the earlier corrected interpreter's output. The installed wheel then rebuilt all prepared populations from the original files, ran all five managed Core analyses afresh and replayed each with standalone Docker. The re-executions matched the earlier native inputs, allele multiplicities, effective arguments and ordered reference/window definitions. Every corrected site numerator, denominator and QC count agreed across execution snapshots. All 397 native integer comparisons between final managed executions and their own direct replays matched exactly. The five detailed records identify acquired R1/R2 order separately from the prepared `input_R1`/`input_R2` filenames. [Installed wheel, source hashes and per-run parity](installed-81c21c8/summary.json)

A common Docker lock serialized the final executions with other qualification runs. The first attempt was stopped after preparation and during the version probe when the lock requirement arrived. The five recorded managed and direct scientific executions all used the shared lock.
