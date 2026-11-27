# Whole-product boundary remediation and real paired-read evidence

## SCI-01 reproduction

The supplied audit used ten 240 bp WT molecules and five 480 bp tandem copies of the intended product. Its paired 248 bp reads independently reconstruct each tandem across a 16 bp overlap. With the audited source at `2f567b8`, the original script reproduced a reportable **5/15** canonical fraction. The molecule truth was **0/10**. Both the original and the repaired executions passed workflow integrity checks. The decompressed physical FASTQ hashes agree across the supplied audit, the reproduced pre-fix run, and the new run. [Before/after counts and source identities](dimer.json)

The corrected paired classifier at `e2ec421` requires the opposing physical mate to identify a unique fragment boundary independently of any reference. It preserves a competing, uniquely reconstructed untrimmed product and reports `COMPETING_UNTRIMMED_PRODUCT`. It reports `UNRESOLVED_READTHROUGH_BOUNDARY` when the physical end placements permit multiple fragment lengths. A read that extends beyond the chosen amplicon can still establish an exact product through corroborating mate evidence.

For the audit input, canonical exact PE was **0/10**. All five tandems stayed in the prepared inventory. The paired family evidence retained the observed sequences and excluded the five tandems. The shared four-template classifier rejected the same molecules. The routed copy’s supplementary exact metric was blocked because its aggregated aligned alleles cannot establish pair-specific removal of the competing products. The genuine CRISPResso2 2.3.4 whole-sample and routed native fractions each remained **0/10**. The sample native archive recorded 15 inputs, ten aligned and five unaligned. [Fixture and assertions](dimer_workflow.py) · [Boundary regression cases](../../../../tests/test_product_boundaries.py)

## EPSPS and barcode-source uncertainty

The independent parser starts from the raw FASTQs, reads the ZIP manifest and checks the reference sequence hashes. It uses standard-library sequence, quality, marker and positional whole-product tests. All expected canonical cells come from its raw WT/intended classification. The actual canonical cells come from the production classifier acting on demultiplexed pairs. The shared assumptions are the supplied 284 bp reference panel, physical mate orientation, 26/27 trimming, unique local context definitions, Q30 thresholds and the two declared copy markers. These agreement tests condition on those assumptions. [Independent oracle](../../../validation/epsps-real/raw_oracle.py) · [Cell and barcode evidence](epsps.json)

| Comparison over 96 recognized index combinations | Total cells | Nonzero | Zero |
| --- | ---: | ---: | ---: |
| Paired joint site states | 1,536 | 228 | 1,308 |
| Four complete templates | 1,536 | 170 | 1,366 |
| Single-site numerator and denominator | 384 | 111 | 273 |
| Canonical WT and intended | 192 | 46 | 146 |
| **Total** | **3,648** | **555** | **3,093** |

All comparisons agreed. The machine-readable result flags WT, edited and unresolved-copy dimensions. Some cells describe the same physical pairs across different scopes. Of 118,742 raw pairs, 114,761 had both indexes recognized and 3,981 had one or both ends unidentified. The empty physical 7G control had zero pairs and no measured fraction.

In physical bin 1A, WT/A-only/B-only/AB counts were **1,957/13/4/9** over complete templates. Concordant joint Q30 counts were **1,990/18/7/19** among 2,034 callable pairs. Among molecules already matching a full template, joint-Q30 retention was **1,018/1,957 WT**, **11/13 A-only**, **4/4 B-only** and **9/9 AB**. The selected joint fraction therefore has observable state-dependent retention. The 26th R1 offset retains a boundary C whose physical origin remains unresolved. The earlier 15/1,562 observation lacks its source read ledger and filters.

| Physical index | Raw pairs | Joint AB / assessable | Full-template AB |
| --- | ---: | ---: | ---: |
| 1A | 5,564 | 19 / 2,034 | 9 |
| 1F | 325 | 1 / 163 | 1 |
| 3D | 8,062 | 1 / 3,297 | 0 |
| ?A (forward index unidentified) | 154 | 1 / 66 | 0 |

These labels identify sequence indexes. Experimental sample identities and the source of the additional signals are unresolved. The `?A` count comes from the raw population outside the 96 recognized index assignments. The aligned CRISPResso counts for 1A depend on the physical mate order and belong to a separate population. [Original EPSPS order-specific evidence](../../epsps-real/README.md)

## ALSW and historical lineage

Under the **211 bp, R1/R2 69/27** hypothesis, the caller and raw positional oracle independently identified **12,488 WT and 4,923 intended**. One pair was too short to apply the trim and 36,484 others were excluded. Under the **253 bp, 27/27** hypothesis, they identified **12,004 WT and 4,734 intended**, with 37,158 exclusions. Each comparison covered the same 53,896 physical molecules. All 107,792 pair-by-hypothesis decisions agree. This retains real overlength support after the boundary guard. Authenticated original target and experimental guide/configuration files remain necessary to select a panel or claim native historical PE parity. [ALSW evidence](alsw.json) · [Historical source limitations](../../v110-forward/README.md)

## Scope, failures and reproduction

- The first corrected dimer M7 attempt used a shared checkout. A concurrent source change triggered `SOFTWARE_CHANGED` at metrics verification. That failed workspace was retained as private diagnostic evidence. The successful rerun used a clean detached `e2ec421` checkout and a new output directory.
- The seven new boundary tests and 149 existing read-through tests passed. They cover unequal edited/reference lengths, swapped and unequal mates, competing molecules, and single- or double-ended overrun with genuine mate-supported boundaries.
- Fresh EPSPS inputs included byte-identical reuploads. One copy per filename was selected after every upload matched its original SHA-256. Each of the five distinct files was rechecked at completion. [Compressed input hashes](validated-inputs.json)
- Run `dimer_workflow.py NEW_DIRECTORY --core PATH_TO_PINNED_CORE` and `compare_candidate.py INPUT_DIRECTORY NEW_DIRECTORY` in the activated test environment. All inputs for `compare_candidate.py` must appear once per filename. For the ALSW check, generate a new pair-call CSV with `v110-forward/compare_alsw.py` from the source under test and pass that CSV to `qualify_alsw.py INPUT_DIRECTORY PAIR_CSV NEW_RESULT_JSON`. The stored findings name the tested source hash; later integrated sources require a new comparison.

## Frozen installed-wheel repeat

The installed wheel built from `81c21c8b7dc536a6e2d1a22d446008407f625415` reproduced the corrected dimer, EPSPS and both ALSW comparisons. The wheel SHA-256 was `5b3cc36ac797cfb9923c02e90a2b860ccfe5ec20dee4d869f8e0f289a882c556`; the package code SHA-256 was `ced81aa6bde707cf992e800671affc235da75c7257b3fc6c39367921e2ec0c4e`. The check compared the installed package bytes against the wheel and reconstructed each dimer-fixture molecule from its untrimmed mate overlap. Ten WT and five tandems gave canonical 0/10. The five tandems remained excluded. [Installed molecular truth](wheel-dimer.json)

Two independent standalone Docker runs reproduced the native full-sample and routed-copy executions. Each matched all 76 scientific integer fields, the allele identity and abundance, reference/window records, effective parameters and runtime identity. Each native run had 15 inputs, ten aligned and zero PE-reference assignments. The first manual-replay launch stopped before starting Docker because its output parent directory was missing. Creating the two parent directories resolved the harness failure. [Full-sample direct comparison](wheel-dimer-direct-target.json) · [Routed-copy direct comparison](wheel-dimer-direct-copy.json)

The installed paired classifier and independent raw oracle agreed on each of the 5,564 physical 1A pairs. They found 1,957 WT, 9 intended and 3,598 excluded from the canonical comparison. The 7G control had zero inputs and no assessable denominator or fraction. Across recognized bins 555 of 3,648 compared cells were nonzero and discrepancies were zero. The unidentified `?A` bin retained one joint AB among 66 assessable pairs. The independent ALSW oracle matched the installed caller for all 107,792 pair-by-panel decisions. At completion, both uploads of each of the five input files matched the frozen compressed-byte hashes. [Installed real-data evidence](wheel-real.json)
