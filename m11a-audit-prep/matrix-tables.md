## Z — Zero execution

| ID | Attack / control | Required observation | Severity if violated |
|---|---|---|---|
| Z01 | Open New Analysis with Core absent | Setup loads; no executable/version probe, subprocess or runtime-qualified claim | BLOCKING |
| Z02 | Validate complete raw PE draft | Strict metadata/file validation only; all scientific executor traps remain zero | BLOCKING |
| Z03 | Validate complete nuclease draft | Pure NucleaseTarget/window/expected-argument helpers allowed; no Core | BLOCKING |
| Z04 | Preview PE insertion/deletion | No geometry-triggered route_pair trials; honest annotation-unavailable state if no safe helper | BLOCKING |
| Z05 | Preview M2 analyze draft | Read-only archive verification allowed; no preparation, route, metrics, locks or sessions | BLOCKING |
| Z06 | Repeat preview many times | No background execution, demux dry-run or automatic native report creation | BLOCKING |
| Z07 | Trap captured aliases/default arguments | Patch bindings and trace original function code; swallowed exceptions still count as forbidden attempts | BLOCKING |
| Z08 | Trap subprocess from provenance/capabilities | Request-scoped git/version probes fail the zero-subprocess rule; bootstrap provenance must be distinguished and documented | BLOCKING |
| Z09 | Attempt resume/force/submit via forged setup request | Unsupported operation rejected; no recovery or workflow mutation | BLOCKING |
| Z10 | Check expected versus observed runtime fields | Expected 2.3.4/profile/digest may be displayed; actual installed version/resolved Core args cannot be certified without execution | MAJOR |

## R — Draft revision races

| ID | Attack / control | Required observation | Severity if violated |
|---|---|---|---|
| R01 | A valid validation arrives after a newer invalid edit | Immediately invalidate current validation/Review; late valid A never enables it | BLOCKING |
| R02 | A invalid validation arrives after a newer valid edit | Late A cannot overwrite new errors or new validation status | MAJOR |
| R03 | Preview PE A pending then switch to nuclease | A is ignored; no PE geometry or identity appears under nuclease | BLOCKING |
| R04 | Review visible then target changes | Plan unavailable synchronously on edit, before debounce/network reply | BLOCKING |
| R05 | Sample identity changed after validation | Revision advances; old source mapping/plan cannot be current | BLOCKING |
| R06 | File bytes change with same path/size/mtime | Content hash changes or source-change failure; stat-only identity is insufficient | BLOCKING |
| R07 | Two preview responses return in reverse order | Only response matching current draft ID/revision and submitted content identity is accepted | BLOCKING |
| R08 | Close draft and create a new one before old response returns | A response from old draft ID cannot attach to new draft even when revision numbers match | BLOCKING |
| R09 | Abort request but server completes anyway | Abort is not the correctness mechanism; stale response checks still hold | BLOCKING |
| R10 | Repeated identical draft requests | Same scientific identity; request IDs/revisions may differ without changing science digest | MAJOR |

## M — Mode contamination

| ID | Attack / control | Required observation | Severity if violated |
|---|---|---|---|
| M01 | PE→nuclease→PE | Preserve or discard inactive data deliberately; only active-mode payload affects preview | BLOCKING |
| M02 | Nuclease→PE→nuclease | Restored active window/profile must be explicitly revalidated, never restored as current validity | BLOCKING |
| M03 | Forge nuclease request carrying PE references/guides | Active nuclease payload rejects PE extras; explicitly separate saved inactive draft data may be retained but never enters identity | BLOCKING |
| M04 | Forge PE request carrying TIGR fields | Inactive TIGR/qwc selection cannot change PE target, preview or plan | BLOCKING |
| M05 | Switch TIGR→explicit window | Clear active profile/target/window binding; backend rejects both selectors submitted as active | BLOCKING |
| M06 | Switch explicit→TIGR | Old explicit qwc cannot override backend-selected W1–W4 | BLOCKING |
| M07 | Switch multicopy PE→single-copy nuclease | No silent merge or leftover copies; explicitly valid single-copy target or blocking error | MAJOR |
| M08 | Edit inactive saved mode fields | Active scientific identity unchanged; switching back requires fresh validation | MAJOR |

## S — Samples and input source

| ID | Attack / control | Required observation | Severity if violated |
|---|---|---|---|
| S01 | Missing R1 | BLOCKING INVALID for raw mode; no valid plan | BLOCKING |
| S02 | Missing R2 | BLOCKING INVALID for raw mode; no valid plan | BLOCKING |
| S03 | R1 equals R2 or same inode/hardlink | BLOCKING INVALID; identity checked before execution, not by calling demultiplex | BLOCKING |
| S04 | Nonexistent input | BLOCKING INVALID; do not manufacture file hash or accept basename alone | BLOCKING |
| S05 | Swapped mates with /1 /2 or CASAVA annotations | BLOCKING INVALID after read-only paired_fastq check; wrong mate annotation | MAJOR |
| S06 | Swapped unmarked mates | VALID WITH WARNING when otherwise synchronized; orientation cannot be inferred from filenames; explicit role confirmation | MINOR |
| S07 | Malformed CSV header/row/barcode DNA/duplicate column | BLOCKING INVALID with row/column evidence from loader | MAJOR |
| S08 | Duplicate forward/reverse pair | BLOCKING INVALID; shared one-sided barcode alone remains allowed | MAJOR |
| S09 | Duplicate stable barcode_id, including casefold collision | BLOCKING INVALID; do not silently sanitize/renumber | MAJOR |
| S10 | Duplicate biological display sample_name | BLOCKING INVALID under current load_samples, despite being a display-facing field | MAJOR |
| S11 | Repeated editor/treatment/dpi condition with distinct biological replicates | VALID; presentation may group it; must not merge biological rows | MAJOR |
| S12 | Repeated biological_replicate within condition and target | BLOCKING INVALID for end-to-end readiness; metadata loader accepts but M5 later rejects; do not run M5 to check it | MAJOR |
| S13 | Blank editor/treatment/dpi | BLOCKING INVALID; no implicit control dpi or editor default | MAJOR |
| S14 | Extra valid expected sample-sheet row absent from reads | VALID WITH WARNING or explicitly unassessed assignment; no invented assigned counts; do not auto-drop the sample | MAJOR |
| S15 | Unused authoritative barcode catalog entry | VALID, normally PRESENTATION-ONLY; full catalog is deliberately broader than expected sample pairs | MINOR |
| S16 | Unknown catalog ID or conflicting barcode sequence | BLOCKING INVALID; no fuzzy correction/rescue of metadata | MAJOR |
| S17 | FASTQ expected-barcode mismatch without running demux | VALID WITH WARNING that assignment is unassessed; no Ready badge claiming barcode coverage was proved | MAJOR |
| S18 | Read length at/below preparation trim | BLOCKING INVALID once established for the relevant prepared population; length==trim produces empty reads; no preparation execution | MAJOR |
| S19 | Valid verified M2 archive | VALID input source analyze; source files remain immutable; raw R1/R2 inactive | MAJOR |
| S20 | M2 read length at/below requested trim | BLOCKING INVALID for that archived sample; read-only inspection only | MAJOR |
| S21 | Mutated source after validation | BLOCKING INVALID until refreshed identity and current validation; no stale plan reuse | BLOCKING |
| S22 | Symlink or source path outside approved roots | BLOCKING INVALID; opaque input handles cannot be forged into arbitrary paths | BLOCKING |
| S23 | Same basename inputs from different directories | PRESENTATION-ONLY disambiguation; IDs/hashes map each source correctly | MAJOR |
| S24 | Paired-end sequencing versus paired statistical design | Independent controls; paired=true requires block_id, not inferred from R1/R2 | MAJOR |

## P — PE target

| ID | Attack / control | Required observation | Severity if violated |
|---|---|---|---|
| P01 | Simple SNP | Target accepts; pure geometry substitution annotation must equal PE_SNP_ANNOTATION golden | MAJOR |
| P02 | Multiple substitutions | Model accepts; exact supplied intended reference remains authoritative | MAJOR |
| P03 | Insertion | Model accepts; do not execute experimental routing qualification to preview | BLOCKING |
| P04 | Deletion | Model accepts; no arbitrary indel-length cutoff or frontend reconstruction | BLOCKING |
| P05 | Mixed multiple intended differences | Model accepts; preserve exact intended product; missing safe annotation is explicit | MAJOR |
| P06 | Invalid DNA ambiguity/gap/internal space | BLOCKING INVALID; only A/C/G/T reference alphabet; RNA U normalization is guide-specific | MAJOR |
| P07 | WT identical to intended | BLOCKING INVALID; no intentional edit exists under Target contract | MAJOR |
| P08 | Missing spacer | BLOCKING INVALID even though other fields look complete | MAJOR |
| P09 | Malformed spacer | BLOCKING INVALID for alphabet; a well-formed absent spacer is a separate preflight issue | MAJOR |
| P10 | Missing extension | BLOCKING INVALID; no inferred PBS/RTT/extension | MAJOR |
| P11 | Missing nicking guide | VALID under Target; do not invent a requirement or a guide | MAJOR |
| P12 | Reverse-only spacer | Model accepts but qualified pure preflight rejects PE_GUIDE_ORIENTATION_UNSUPPORTED; do not reverse supplied experiment to rescue | MAJOR |
| P13 | Wrong shared guide/extension across copies | Backend geometry rejects inconsistent experiment; no silent per-copy guide synthesis | MAJOR |
| P14 | Duplicate copy, casefold identity, duplicate/reverse-complement WT | BLOCKING INVALID at the appropriate collection/geometry gate | MAJOR |
| P15 | Homeolog ambiguity with insufficient pair diagnostics | Schema-valid does not mean copy routing SAFE; display backend-supported unresolved/blocked state, never claim eligibility | MAJOR |
| P16 | PE qwc sentinel 0 | Legacy PE model accepts it; not a nuclease explicit coordinate; scope/qualification caveat must remain visible | MAJOR |

## N — Nuclease target

| ID | Attack / control | Required observation | Severity if violated |
|---|---|---|---|
| N01 | Normal explicit 10-20 | Valid, zero-based inclusive; expected intervals [[10,20]] | MAJOR |
| N02 | Literal explicit sentinel 0 | BLOCKING INVALID with NUCLEASE_WINDOW_REQUIRED | BLOCKING |
| N03 | Real explicit 0-0 | Valid one-base coordinate, no false sentinel rejection | MAJOR |
| N04 | Reversed 20-10 | BLOCKING INVALID | MAJOR |
| N05 | Out of range 59-60 on 60nt WT | BLOCKING INVALID | MAJOR |
| N06 | Ordered disjoint multi-interval 1-3_8-10 | Valid; not a single-window-only GUI rule | MAJOR |
| N07 | Overlapping/unordered intervals | BLOCKING INVALID, no frontend sorting/repair | MAJOR |
| N08 | Boundary 0-59 or 59-59 | Valid within 60nt WT; no PE end-exclusion rule applied | MAJOR |
| N09 | TIGR forward target | Exact golden physical locus, forward labels and intervals | MAJOR |
| N10 | TIGR reverse target | Same physical-locus coordinate rules; target-oriented labels swap; no frontend reverse math | MAJOR |
| N11 | TIGR palindrome | One physical locus; orientation palindromic, directional labels and between-cut target-oriented sequence null | MAJOR |
| N12 | TIGR absent target | BLOCKING INVALID, TIGR_TARGET_MISSING | MAJOR |
| N13 | TIGR multiple physical matches | BLOCKING INVALID, TIGR_TARGET_NOT_UNIQUE | MAJOR |
| N14 | TIGR W1/W2/W3/W4 and omitted W2 | All four advertised choices match independent goldens; W2 only default | MAJOR |
| N15 | TIGR length not 18 or non-DNA target | BLOCKING INVALID; U not accepted for nuclease DNA | MAJOR |
| N16 | TIGR W4 clipped at left/right edge | Match clipped golden intervals exactly, not negative/out-of-bounds coordinates | MAJOR |
| N17 | Multiple nuclease copies or PE tolerance policies | Production scope unsupported; schema/model validity cannot be promoted to a supported plan | MAJOR |

## I — Deterministic identity

| ID | Attack / control | Required observation | Severity if violated |
|---|---|---|---|
| I01 | Same normalized scientific draft twice | Identical canonical scientific payload/digest; response revision/request metadata separate | MAJOR |
| I02 | Change UI step/filter/selection/zoom/sort | Scientific identity unchanged | MAJOR |
| I03 | Change input bytes preserving name/path/size | Scientific source identity changes or mutation invalidates | MAJOR |
| I04 | Change barcode assignment | Input/scientific identity changes, stable sample join remains barcode_id | MAJOR |
| I05 | Change WT/intended/copy/target identity | Active target scientific identity changes | MAJOR |
| I06 | Change TIGR window or explicit qwc | Active normalized scientific identity changes | MAJOR |
| I07 | Omitted W2 versus explicit W2, 010-020 versus 10-20 | Equivalent normalized nuclease identity; exact source-file identity may still differ | MAJOR |
| I08 | Reorder semantically equivalent sample/copy rows | Sorted DAG semantics stable; source byte hashes may change and must not be erased | MAJOR |
| I09 | Change report title/output destination | Distinguish report/execution identity from science-only subset; do not falsely require full M7 Plan hash invariance | MAJOR |
| I10 | Change sample_name/editor/treatment/dpi/biological replicate | Real metadata is not presentation-only; current conservative lineage/statistical grouping changes | MAJOR |

## O — Destination safety

| ID | Attack / control | Required observation | Severity if violated |
|---|---|---|---|
| O01 | Nonexistent destination | VALID if authorized/separate with suitable existing ancestor; preview creates no path or parent | BLOCKING |
| O02 | Existing empty directory | BLOCKING INVALID for a new run, because execute_workflow rejects any existing root | MAJOR |
| O03 | Existing unrelated nonempty directory | BLOCKING INVALID; no adoption/overwrite/deletion | BLOCKING |
| O04 | Existing PEAnalyzer workspace | BLOCKING INVALID as a new output; may offer Open Existing, never implicit resume/force | BLOCKING |
| O05 | Symlink destination or ancestor | BLOCKING INVALID; no follow-through creation | BLOCKING |
| O06 | Traversal/absolute child/backslash attack | BLOCKING INVALID at approved-root/path gate; no_symlinks alone is not traversal rejection | BLOCKING |
| O07 | Read-only parent | BLOCKING INVALID when demonstrable; use non-root OS oracle; no create/delete writability probe in science destination | MAJOR |
| O08 | Destination equals or contains inputs/source directory | BLOCKING INVALID; no output/input overlap, no archive mutation | BLOCKING |

## V — Review fidelity

| ID | Attack / control | Required observation | Severity if violated |
|---|---|---|---|
| V01 | Mode/sample count/stable IDs | Render exact backend preview values; count biological rows, not files or reads | MAJOR |
| V02 | Target and PE copy count | Group one target with its real copies, not one target per row | MAJOR |
| V03 | Nuclease profile/window/qwc/configuration | Render backend-normalized fields/expected profile; no generic hardcoded W2 | MAJOR |
| V04 | Scientific identity and validation revision | Show only latest validated payload and matching revision; never derive a second JS identity | BLOCKING |
| V05 | Stage graph | Match backend nodes/dependencies; nuclease routing slot labelled single-copy identity | MAJOR |
| V06 | Marked backend response oracle | Inject distinctive valid preview fields/coordinates/IDs; Review uses supplied values, not independently reconstructed geometry | MAJOR |

## U — Hidden errors and accessibility

| ID | Attack / control | Required observation | Severity if violated |
|---|---|---|---|
| U01 | Invalid sample filtered out | Global blocking summary remains; error action clears/reveals filter and focuses correct row | MINOR |
| U02 | Invalid row below viewport/page | Error navigation reveals the row and usable focused field, not an offscreen node | MINOR |
| U03 | Invalid field on another step | Review blocked; summary takes user to that step and field without deleting draft | MINOR |
| U04 | Several invalid fields | Stable useful first error, remaining errors discoverable; focus not trapped | MINOR |
| U05 | Press Review immediately after edit | Invalidation synchronous; cannot outrun debounce or reuse cached prior validity | BLOCKING |

## G — Small M10 regression boundary

| ID | Attack / control | Required observation | Severity if violated |
|---|---|---|---|
| G01 | Open existing PE fixture | Existing full-open verification and viewer remain usable; setup executors still unavailable | MAJOR |
| G02 | Open existing nuclease fixture/Overview | Stored data and mode remain unchanged | MAJOR |
| G03 | Navigate five result tabs | Existing snapshot-based navigation retained; no broad re-audit | MINOR |
| G04 | Mutate one opened artifact | Existing changed-workspace failure and hide-results behavior retained | BLOCKING |
| G05 | Edit setup draft while viewer has an open workspace | Draft mutations cannot change cached result, source handles or selected workspace identity | BLOCKING |
| G06 | Switch New Analysis↔Open Existing repeatedly | State namespaces stay separate; stale preview cannot be shown as existing scientific result | BLOCKING |

## K — Packaging and offline

| ID | Attack / control | Required observation | Severity if violated |
|---|---|---|---|
| K01 | Record stable candidate HEAD | No final PASS until implementer declares stability; record exact parent/diff/version | INFO |
| K02 | Validate production source/asset identity | Existing build gate remains active after setup frontend changes | MAJOR |
| K03 | Build clean checkout wheel | Includes setup and reader production assets; no editable-source leakage | MAJOR |
| K04 | Build sdist and wheel from sdist | Required frontend inputs, build script and assets all present | MAJOR |
| K05 | Missing/stale asset attack | Packaging fails explicitly instead of making viewer-less/old-setup wheel | MAJOR |
| K06 | Install into fresh environment outside checkout | Imports/assets come from site-packages; load setup and existing viewer | MAJOR |
| K07 | Runtime PATH without Node and CRISPResso | Both modes load and setup validates/previews without subprocess/backend attempts | BLOCKING |
| K08 | Offline browser/no arbitrary filesystem access | Local assets only; foreign Origin/Host and forged file handles rejected; no new unrestricted file server | BLOCKING |
