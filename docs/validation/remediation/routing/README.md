# F-01 routing, 33-nt insertion and reverse-strand qualification

## Editing-state-dependent routing

The independent audit's original script was run against a fresh archive of `2f567b8`, then repeated on the candidate. Both replays generated the same raw FASTQ bytes as the deposited audit. The original reference geometry was SAFE and the verifier accepted a cohort of 50 WT and zero PE pairs. The 50 intended insertion pairs were all quarantined. The original full prepared sample contained 50 WT and 50 PE. Source and input hashes are in `f01-input-proof.json`.

The candidate keeps these physical cohorts and their counts. For each observed mate-length pair and strand, a matched WT/PE control now exercises the production router on the same panel. Unresolved orientation exercises both possibilities. Known extension-converted states are included where appropriate. A difference in acceptance blocks the affected copy efficiencies. A cross-copy assignment blocks both source and recipient. The verifier regenerates this evidence from the prepared input. The F-01 control returned WT assigned and PE unassigned at 123/123 nt. Both copy-native and copy-exact efficiencies are unavailable with `EDIT_STATE_SELECTIVE_COPY_ROUTING`. Genuine all-prepared native and independent paired exact counts are each 50/100.

The proposed `f658b22` patch identified the observed-length gap. Its early routing exception would discard the routing partition, and its forward-only controls omit physical orientation and editable marker states. The qualification tests now include reversed orientation, asymmetric mates, deletion, a 33-nt insertion, different copy lengths, repetitive controls, a convertible marker, and tampering with the recorded gate. This gate checks perfect amplicon-end controls with the observed mate lengths. Biological noise, internal fragment termini and unmodeled alleles remain sources of uncertainty.

## Synthetic insertion

A fixed independent random amplicon received a synthetic 33-nt insertion. This is a HiBiT-sized fixture. A predeclared base constraint makes the insertion junction unique. An initial synthetic spacer/extension placement failed the backend's strand check. The accepted synthetic fixture includes the complete spacer in its template segment and retains the native sequence checks.

The 37 prepared pairs yielded 36 post-preprocessing and 35 aligned reads. Native PE assignment was 27/35. The aligned allele table independently gave 8 exact WT, 7 exact intended, 6 partial intended inserts, 5 alternate inserts of the same length, 4 intended inserts with flank substitutions, 3 unexpectedly longer products and 2 exact tandem inserts. Paired-read exact classification was 7/15. One insufficient-overlap pair and one ambiguous reconstruction were unassessable. The test compares each pair against the original physical fragment truth. Junction-dependent classifications require a unique simple insertion coordinate.

## Synthetic ALSP-like strand and extension polymorphism

The complete prepared population contained 35 paired fragments. Both supplied reference orientations gave a native PE-reference fraction of 22/35 on the valid anchor. Both secondary-copy cohorts contained 8 WT, 7 intended products retaining the natural variant, 6 intended products carrying the converted base and 5 other products. The six converted molecules kept their independently verified copy assignment. Two marker mosaics were quarantined. The mismatched secondary PE anchor remained unsupported. These are synthetic outcomes. The original ALSP P193S experiment still needs its actual references, FASTQs and authenticated metadata.

## Native and installed-wheel evidence

The ten completed native runs each have an independent pinned-Docker replay. Their original and replayed allele tables agreed in every row identity, integer abundance, reference sequence, effective window, effective scientific argument, and reported integer. The installed wheel independently re-read all twenty native result sets, verified raw mate hashes against the replays, replayed routing eligibility, reclassified the synthetic insertion pairs, and rebuilt the reported metrics from the preserved authoritative outputs. `result.json` contains the wheel and source hashes and a per-run summary. The compressed `native-evidence.json.gz` includes complete native manifests, replay parity receipts and installed-wheel recounts. An optional additional frozen pre-fix Core run timed out at its version probe. The pre-fix evidence uses the independently reproduced physical partition and original verifier acceptance.

Eight targeted tests passed. The accompanying routing/metrics regression run passed 168 tests. The integration scripts use fresh output directories and preserve the original files.
