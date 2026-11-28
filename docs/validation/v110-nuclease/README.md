# Multi-copy nuclease regression

The fixture uses two synthetic amplicons with six distinguishing SNPs and a three-base offset between the TIGR target coordinates. The copy labels chr03g and chr13g identify simulated inputs. The historical NbPDS Pool1 EV and Pool2 ParTasR FASTQs, target panel and original run metadata were unavailable. Their biological editing rates and copy assignments remain unverified.

| Measurement | Combined indel reads / assessable reads | chr03g | chr13g | Copy-ambiguous reads included / observed |
|---|---:|---:|---:|---:|
| Primary TIGR W2 | 3/16 | 1/6 | 1/7 | 3/3 |
| Exploratory TIGR W3 | 4/16 | 1/6 | 2/7 | 3/3 |
| Distinct explicit reference windows | 3/13 | 1/6 | 2/7 | 0/3 |

Each case starts with the same 17 read pairs. One pair is unaligned against either reference. The three ambiguous reads contain conflicting flanking markers. W2 spans 104–113 in chr03g and 107–116 in chr13g (zero-based inclusive). A single chr13g deletion outside W2 enters W3. An independently specified single-base insertion, inside-W2 deletion, substitution and known WT controls exercise the remaining counts.

## Measurement

For each copy, run Core 2.3.4 with its own WT reference and the window derived from that reference. The single-reference parser checks the resolved scientific arguments, window indices, preprocessing and alignment counters, detailed allele integers and original prepared input identities. The identical merged sequence inventory from all runs defines physical multiplicities. Each distinct merged sequence and its multiplicity enters the combined measurement at most once. Rejected preprocessing pairs, pairs unaligned everywhere and aligned reads with an unresolved window call remain identifiable.

Assignment uses exact 11-base words containing one diagnostic SNP and unique bilateral flanks in each competing reference. It requires evidence at two independent SNP positions against every competing copy, with no contrary marker. For TIGR, all W1–W4 analyses exclude the entire W4 interval and overlapping marker flanks. Large events or sequencing errors can remove marker evidence. Copy-specific estimates are conditional on confident origin and assessable window coverage. Confident reads enter only under their assigned reference's Core calls. Reads of unknown origin can contribute to the combined estimate only if all reference runs align them, the local WT contexts and physical window footprints agree, and the detailed window event signatures agree. Otherwise they enter the aligned-unassessable count. The selected conditional denominator is displayed with every fraction.

The default W2 primary outcome, the exploratory W3 outcome and differing explicit windows are separate measurements. To compare matched stored results:

```sh
peanalyzer compare-nuclease-windows --primary W2/metrics/bc001/T1/result.json --exploratory W3/metrics/bc001/T1/result.json
```

The command checks identical prepared input checksums, copy identities, WT sequences, TIGR target definitions, runtime and sample identity. It emits the fraction and source result hash for each window.

## Reproduction

```sh
M8_INTEGRATION=1 M3_CORE_EXECUTABLE=peanalyzer-crispresso pytest -q tests/test_multicopy_nuclease.py
```

The test generates the inputs and defines expected molecule counts independently before executing the normal workflow, statistics, report and output verifier. The pinned image digest and exact counts are recorded per case in the oracle files. The archived evidence contains all six genuine Core outputs needed by the strict parser, the retained merged FASTQs and corresponding aggregate result JSONs. The ordinary test suite reparses that evidence offline.
