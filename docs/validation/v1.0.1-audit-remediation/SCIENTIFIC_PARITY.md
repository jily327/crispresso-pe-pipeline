# Scientific parity

The audited baseline was installed separately at version 1.0.0; the candidate is 1.0.1. Both executed the Fable seeded four-sample known-truth PE design through the genuine qualified Docker image. The independent verifier passed **76/76 checks on each version**, including molecule counts, exact/native denominators, raw backend assignments, biological-sample statistics, exact contrasts/BH adjustment and report tables.

The candidate's additional independent layer comparison passed **59/59 checks** across metrics, copy eligibility/QC/product evidence, stored observations/group summaries/contrasts, an actual loopback HTTP server, and the exported workbook. `compare_layers.py` is retained as a runnable artifact. Only population IDs and source-result identity fields are excluded from baseline-to-candidate equality: their hashes necessarily bind version/path-dependent provenance. No scientific counts, classifications, statuses, exclusions, fractions or statistics are excluded. Same-run HTTP/XLSX comparisons use the authoritative stored numerator/denominator pair; XLSX fractions allow only decimal serialization rounding at 1e-14.

| Sample | Exact intended PE | Native PE |
|---|---|---|
| 1A | 0 / 400 | 0 / 430 |
| 2A | 3 / 303 | 3 / 318 |
| 3A | 100 / 300 | 180 / 470 |
| 4A | 150 / 250 | 155 / 395 |

Exact intended PE remains `exact intended PE / (exact WT + exact intended PE)`. Native PE remains `Prime-edited-reference reads / all aligned reads`. The differing 3A values are intentional. Both use biological samples as the statistical units. No unavailable measurement becomes zero; blocked copy measurements remain distinct from target-wide primary results.

No scientific algorithm file changed. The only changes in report modules are an explanatory provenance paragraph in `reporting.py` and the displayed provenance column label in `nuclease/reporting.py`. `workflow_models.py` and its stage schema clarify the existing runtime field's description, without adding a default or changing serialized historical models. Workflow staging and empty-input checks surround the existing scientific runners. `metrics/production.py`, backend runners/parsers, demux, alignment, routing, reconstruction, nuclease classification/window geometry, statistics, and metric definitions are unchanged from the audited baseline.

The real PE/nuclease HTTP integration tests also passed (2 tests). The broader genuine-backend matrix is reported in TEST_MATRIX.md; do not infer coverage from a disabled integration marker. All parity data here are synthetic, not laboratory samples. Windows Excel was not executed; workbook values were independently read using openpyxl.

The Fable nuclease W2 and W4 designs were also run on both versions. Each independent oracle passed 36/36 checks; stored metrics, class counts, aligned/unaligned counts, net-size fractions and allele rows match exactly between versions (see evidence/nuclease-parity.json). The upstream zero-net-length substitution behavior is preserved.
