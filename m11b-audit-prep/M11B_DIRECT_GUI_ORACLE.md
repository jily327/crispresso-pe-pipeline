# Review-to-execution and direct-versus-GUI oracle

## Three linked identities

1. **Review:** independently capture immutable draft ID/revision/content and `PlanPreview`, including `scientific_identity_sha256`, `plan_identity_sha256`, decoded samples/inputs/configuration/backend FieldValues, full targets and output proposal. Preserve the exact registered source bindings on the server side. Display text is insufficient.
2. **Accepted submission:** capture the actual HTTP request/response and accepted immutable job binding. Revision and both hashes must equal the current Review. Recheck source bytes, archive identity and absent/contained destination at acceptance AND before worker execution. Later draft editing must not mutate the accepted snapshot. Job JSON is corroborating evidence only.
3. **Executed workflow:** independently load `workflow/plan.json`, `workflow_manifest.json`, every referenced stage manifest, metadata snapshots, M4 results, statistics and report provenance, and call the existing `verify_workflow_output`. Match semantic Review fields to these existing artifacts. An M11B receipt alone is never proof.

`scientific_identity_sha256` hashes the M11A normalized object: mode/source_mode; sorted typed samples; full scientific targets; source evidence; full default demux config; effective preparation trims; qualified routing identity (or nuclease single-copy identity); `statistics=summarize`; expected backend. `plan_identity_sha256` also binds analysis name and the hash of the resolved output path. These are not the same schema as the M7 plan hash. Comparing those two unrelated hashes for equality is wrong.

`identity_oracle.py` reconstructs the Review science digest from frozen draft targets, typed sample normalization, decoded Review fields and current baseline contracts; checks the accepted revision/draft/hashes/output; calls the existing workflow verifier; compares executed samples/targets/config/trims/mode/source hashes/runtime and report source bytes. It is an independent auditor script, not a production job endpoint. Use the pinned backend for baseline reconstruction and confirm candidate science files remain identical. It does not prove HTTP authorization, a process tree, timing, or all child qualification fields by itself; the checks below are mandatory.

| Scientific intent | Independent executed proof |
|---|---|
| Barcode identity, biological conditions/replicates, pairing/block | `Plan.samples`, exact samples snapshot hash, `expected_samples`, M4 internal `sample_id`, M5 `sample_metadata_hash`, observations/provenance. Do not join display sample name. |
| Target/copy/mode/reference/PE/spacer/extension/scaffold | Full `Plan.targets`, `normalized_options.scientific_configuration`, stage parameters, M4 `provenance.target_definitions_sha256`; verify exact strings/defaults. |
| Raw input bytes | Review SHA/size and independently streamed source SHA/size; `Plan.inputs.r1/r2`, source-node output, demux lineage. Equal counts are insufficient. |
| External M2 archive | Review whole-tree inventory digest and independent archive snapshot; existing M2 verifier; M7 per-file input identities, sample/barcode inventory and prepared lineage. Never mutate/copy-over archive. |
| Demux catalog/config and prep | Full default config, bundled catalog hash if applicable, normalized sample barcodes, analysis manifest effective `r1_analysis_trim_5p` and `r2_analysis_trim_5p`. `None` requested automatic trim is not a changed effective trim: verify resolution from the archive. |
| PE routing | Qualified policy identity, geometry/scientific gate artifact or verified routing manifest, sample/target/analysis lineage. Warning may become explicit scientific quarantine; it is not permission to change thresholds or assign copy. |
| Nuclease | Complete `scientific_identity`, selected window/intervals/zero-based-inclusive qwc, all 58 locked backend settings, actual child resolved arguments in `CRISPResso2_info.json`, command evidence and qualification results. Single-copy identity is not PE routing. |
| Backend | `Plan.backend_identity` executable path/hash, version exactly 2.3.4 and qualified runtime digest; actual worker executable/resolved settings and child provenance. An expected preview version is not proof. |
| Statistics | `summarize` only for existing M11A; no hidden contrast/policy files; exact manifest coverage, M5 input-result hashes, biological sample unit, preserved blocked/null status. |
| Report | M6 source/result bytes exactly equal workflow statistics/result; source hash, all artifact hashes, SVG XML and HTML inclusion; current viewer registration invokes existing verification. |

The child qualification check must preserve existing ambiguous/discarded-population gates and insertion semantics, including both anchors in the selected nuclease window. Fail on an unexplained resolved setting even if final fractions happen to match.

## Committed synthetic inputs

`fixtures/pe`: four biological samples, treatments A/B, two replicates each, one target T1/two copies, 24 pairs per sample, 96 total. Ground truth PE-origin counts are 4/8/16/20, with WT complement. These are molecule origins, **not assertions that every metric denominator or backend acceptance equals raw counts**. Existing authoritative stages determine attrition and reportability.

`fixtures/nuclease`: same four-sample design, one copy, 20 pairs per sample/80 total; deletion-origin counts 2/4/14/16. A unique 18-nt TIGR target starts at 100 in a 240-nt WT reference. W2 is `104-113`; W1 `104-105_112-113`, W3 `100-117`, W4 `90-127`. `truth.json` records the selected geometry and settings. Test explicit coordinates as a separate representation and each named window; do not infer biological efficiency from the fixture's construction ratios.

Both use custom exact inline barcodes, explicit 8/8 preparation trims, paired input and descriptive summaries. Config and PE target defaults have been normalized to the actual M11A-exposed contract. Templates intentionally leave registered opaque input/output IDs unset. Fill them through the server's local registration, not arbitrary browser paths. Input FASTQs are deterministic gzip with synthetic identifiers only. No private data or generated scientific results are included.

`make_fixtures.py` recreates inputs using test designs from the pinned baseline; it invokes no scientific executor. Published fixtures are the frozen oracle inputs; regeneration is optional and must compare all bytes before use. The generator removes unsupported contrast/policy requests.

## Execution procedure

1. Verify package checksums; register fixture inputs and fresh GUI output parent. Import a draft template, obtain current valid Review, capture it with the registered path mapping and source hashes. No science may have run.
2. Direct arm: in the same candidate package/qualified rendering environment, call existing `execute_workflow(**args)` with the committed samples/targets/config/input bytes, explicit 8/8 trims, same title/backend/runtime, no contrasts/policies and `resume=False, force=()`. Resolve relative `direct-arguments.json` paths to the fixture directory and supply a NEW output. Do not pass its placeholder strings verbatim.
3. GUI arm: explicit accepted Run for the captured Review to another NEW output. Use the same backend/runtime/code/dependencies. Capture stage execution arguments without changing them.
4. Verify both workspaces independently. Validate Review→GUI and direct-intent→direct lineage. Compare the inventory below. Differences require exact per-field provenance explanations, not broad normalization.
5. Repeat for analyze mode using a separately verified synthetic demux archive, whose full identity is captured at Review. Never alter that archive; direct and GUI consume it immutably.

## Explicit comparison inventory

| Artifact | Requirement / permitted differences |
|---|---|
| Original raw FASTQs | Exact SHA-256 and size in both arms; no waiver. |
| Samples/targets/config snapshots | Prefer byte identity. If GUI serializer has different formatting, compare full typed content including defaults AND preserve different exact source hashes and their downstream propagation. No changed scientific field. |
| Demux QC/scientific counts and prepared FASTQs | Same terminal/per-sample counts, synchronized IDs, exact decompressed FASTQ records/quality/order. Compare compressed bytes first; a difference needs proven compression-header-only explanation, not payload normalization. |
| Analysis/routing manifests and routing tables | Scientific fields, decisions, reasons, pair identities and effective trims exact. Enumerate legitimate source/root path or downstream hash differences individually. |
| M4 `metrics/<barcode>/<target>/result.json` | Strict model load then full JSON leaf comparison. All metric integer populations, numerators/denominators, fractions, statuses, reasons, product classes, target/window and qualification must match. Root/invocation/software provenance differences may be narrowly evidenced; do not drop the whole provenance subtree. |
| Core info/mapping/allele artifacts | Independently reconcile authoritative populations/settings per existing backend; hash inventory within each arm. Child timing/temp paths may differ; scientific tables and alignment evidence must agree. Native HTML is not authority. |
| `metrics/manifest.csv` | Same complete sorted sample×target paths; no duplicates or missing difficult sample. |
| `statistics/result.json` and TSVs | Exact scientific observations/groups/statuses/means; no contrast invention; all input hashes validated within each arm. Propagated upstream hash changes may differ, but must resolve to the exact corresponding independently verified artifact. |
| `report/source/result.json` | Byte-identical to **its own** statistics result in each arm. Cross-arm equality expected only if the statistics bytes match. |
| Report SVGs/HTML/manifest | Compare actual bytes first in same rendering environment. Same scientific figures/geometry/values/statuses. Embedded source hashes/title/provenance can propagate explained differences; all SVGs XML-valid and inventoried. No blanket HTML-ignore rule. |
| Workflow/stage/session provenance | Paths, timestamps, session IDs, top-level argv and package/git identity may differ legitimately. Document every such difference. Dependencies and signatures must validate within each lineage; timestamps never define science. |

`compare_json.py` defaults to rejecting every difference. A waiver requires an exact JSON pointer, exact left/right value hashes, reason and independent evidence. No wildcard or “ignore all provenance.” Review waivers manually; a valid waiver format does not make a scientific difference acceptable. Equal percentages alone never pass this oracle.
