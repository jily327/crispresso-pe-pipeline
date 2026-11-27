# Nuclease audit remediation ledger

| Item | Observation and correction |
|---|---|
| SCI-03 | The audited candidate checked every base from the first interval start to the last interval end. A known insertion was excluded by an intervening N at an unselected position. Original input hashes and a fresh frozen-candidate workflow are recorded in before.json. Both archived and fresh runs produced combined 0/7, copy a 0/4 and copy b 0/3 and passed workflow verification. |
| Known truth | Four WT a, three WT b and two insertion-bearing a molecules give 2/9 combined, 2/6 a and 0/3 b. The two reads have an insertion within 104–113 and an unknown base at 123, between selected intervals 104–113 and 132–135. The original paired FASTQs and sample/target/config files are preserved in audit-inputs. |
| Correction | Each selected interval requires bounded native alignment evidence. Unknown bases within an interval exclude the observation. A base in the gap between intervals does not change its selected-window observation. Unresolved-origin concordance uses the individual reference contexts, selected physical footprints and original event calls. New results record the observability contract and explicit aligned exclusion reasons. Historical records retain their original validator and integers. |
| Test before correction | A new parameterized interval-boundary regression failed on the audited implementation at the first N just outside the first interval. The genuine audit reproduction generated matching FASTQ bytes and reproduced both missing insertion calls. |
| C4 | The original feature legitimately enabled qualified multi-copy inputs. The former broad exception assertion did not prove early rejection. The replacement requires INVALID_WORKFLOW_INPUT with NUCLEASE_WINDOW_POLICY_MISMATCH and uses fail-on-call guards for backend resolution, preparation, demultiplexing, routing, metrics and stage execution. |
| Native output | Single- and multi-reference runs preserve HTML, standard plots, mapping/quantification files, native allele rows, physical FASTQ inputs and exact argv. The original multi-WT analysis runs on all prepared pairs. Each additional single-WT run uses that same independent population. Only the separate PEAnalyzer-derived combined measurement joins physical read multiplicities. |
| Retry | On the first corrected backend run, all nine test variants produced complete native artifacts, but stage finalization rejected the order of the inventory. The new native sibling HTML file exposed component-order sorting of Path objects. Sorting by POSIX path text satisfies the existing manifest validator without weakening integrity checks. The initial attempts are retained and the complete workflow is rerun in a fresh output directory. |

The integration test generates tagged controls at W1–W4 for one and two copies. It includes an insertion at a cut boundary, a crossing deletion, mixed insertion/deletion, an unknown inside and outside chosen intervals, substitution-only copies, conflicting copy markers, a one-event read and zero events in a positively covered copy. The independent physical_oracle.py decodes each retained merged ID, verifies exclusive sequence multiplicities in the combined and per-copy outputs and checks event indicators against the detailed native tables. Native parity uses the sibling direct_parity.py script to run the preserved manual command against the pinned image.

The original experimental NbPDS Pool1 and Pool2 inputs are unavailable. Results in this ledger describe synthetic molecules.

## Installed-wheel results

The frozen commit was `81c21c8b7dc536a6e2d1a22d446008407f625415`. Wheel SHA-256 was `5b3cc36ac797cfb9923c02e90a2b860ccfe5ec20dee4d869f8e0f289a882c556`. The installed scientific package code hash was `ced81aa6bde707cf992e800671affc235da75c7257b3fc6c39367921e2ec0c4e`. All twelve installed workflows and all 28 externally executed native reproductions passed. Each reproduction used the staged prepared mate bytes and executed the preserved command directly in the pinned Core 2.3.4 image.

| Controlled population | Combined indels / assessable reads | Copy a or chr03g | Copy b or chr13g |
|---|---:|---:|---:|
| Original audit SCI-03 | 2/9 | 2/6 | 0/3 |
| Original primary W2 | 3/16 | 1/6 | 1/7 |
| Original exploratory W3 | 4/16 | 1/6 | 2/7 |
| Original distinct explicit intervals | 3/13 | 1/6 | 2/7 |
| Additional W1 controls | 6/16 | 4/8 | 1/6 |
| Additional W2 controls | 4/14 | 2/6 | 1/6 |
| Additional W3 controls | 4/14 | 2/6 | 1/6 |
| Additional W4 controls | 5/14 | 2/6 | 2/6 |
| Single-copy W1, W2, W3, W4 in four separate runs | 1/9 each | — | — |

Two insertion-bearing molecules in the additional panel have an N in the gap between W1 intervals. Both remain observable in W1. W2, W3 and W4 include the unknown base and each records two explicit selected-interval exclusions. One additional deletion enters only W4. Conflicting copy markers exclude a molecule from each named-copy estimate while the concordant allele evidence permits one combined contribution. True per-molecule identity and multiplicity were checked separately from native reference assignment.

The external native comparisons cover 1,491 integer fields and 209 allele identities across the 28 pairs of executions. Each native run matched its own manual execution on the runtime image, effective parameters, ordered reference sequences, effective windows, allele identities and abundances. The original multi-reference output retains Core's reference assignments. The independent joined combined and named-copy results use their own assessable denominators. For SCI-03 the verified GUI, Excel, measurement HTML and TSV each contained exactly 2/9, 2/6 and 0/3.

[qualification.json](qualification.json) contains all case statuses, counts, installed package identity and hashes. [native-evidence.zip](native-evidence.zip) contains 28 full integer-diff reports, native detailed alleles, mapping and quantification tables, original run information, execution metadata, reproduction scripts and exact synthetic prepared inputs. The archive contains 264 entries. All 56 mate files have synthetic fixture identifiers and each contains at most 17 reads. Complete original native and replay directories including plots and reports were retained under `/workspace/scratch/audit-remediation/nuclease-integrated-1/{managed,direct}`. Archive SHA-256 is `d553bea1b2def93d8e9f6f269c52f41e489f2ed36a8797dba0f09d46eb7daa96`.

The pre-freeze snapshot included stale 1.0.1 distribution metadata and seven early version probes timed out under concurrent Docker load. Those runs were development diagnostics. The seven serial retries succeeded and the definitive twelve workflows ran again with the frozen installed 1.1.0 wheel and a shared Docker execution lock. Run `qualify.py PACKAGE_DIRECTORY NEW_DIRECTORY` to repeat the managed and direct executions. `collect.py NEW_DIRECTORY EVIDENCE_DIRECTORY` checks the original artifacts, direct comparisons, and export integers and writes the compact evidence.
