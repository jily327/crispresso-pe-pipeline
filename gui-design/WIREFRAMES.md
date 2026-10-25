# Low-fidelity wireframes

ASCII review artifacts only; no frontend implemented. Brackets denote controls or backend-returned values. Values marked “illustrative” are layout examples, not measurements from the supplied biological report. Fourteen primary screens; PE/nuclease variants and drawers do not add screens.

## P0 — Analyses library

```text
PEAnalyzer                                  Runtime: [verified version]    [Help]
Analyses                                                    [+ New analysis]
[Search]   [State: All]   [Mode: All]                         [Open workspace]
Name             Mode             Target       State                 Updated
Lab study        Precise Edit     [target]     Completed · limits     [time]
Nuclease draft   Indel / Nuclease  [target]     Draft                  [time]
Interrupted run  Precise Edit     [target]     Incomplete              [time]

Selected analysis: [Open] [View provenance] [Duplicate as new draft]
A directory is not a completed analysis. Existing work is verified before use.
```

Project/group labels are optional catalog organization, not another scientific hierarchy or pooling operation.

## S1 — Samples & sequencing

```text
New analysis                         1 Samples  2 Mode  3 Target  4 Config  5 Review
Input source: (*) Raw paired FASTQ   ( ) Verified demux archive
Sequencing: Paired-end [qualified; no single/interleaved controls]
R1 [selected local file · size · Checking/Verified]    [Browse local] [Copy upload]
R2 [selected local file · size · Checking/Verified]    [Browse local] [Copy upload]
Suggested mate match: [confirm]       Record synchronization: [backend result]

Sample metadata    [Import CSV] [Template] [Add row]    [4 biological samples]
Name   Stable ID   F barcode   R barcode   Editor   Treatment   dpi   Bio rep
[...]  [...]       [...]       [...]       [...]    [...]       [...] [...]
Paired experimental design [explicit choice]   Block ID [conditional]
Library [qi_hitom_v1 / Custom]   Matching: Exact [locked]   [Advanced layout]
[Row 3: duplicate stable ID → focus cell]                  [Validate metadata]
                                                        [Save draft] [Next]
```

Analyze variant replaces R1/R2 with a verified archive selector, summary hash and sample inventory. It does not say “Upload prepared reads.” The metadata table remains required. Detailed columns scroll inside the table; mandatory metadata never disappears from validation.

## S2 — Mode selector

```text
2 / 5 · Analysis mode
+------------------------------------+  +------------------------------------+
| ( ) Precise Edit                   |  | ( ) Indel / Nuclease               |
| Qualified prime-editing analysis   |  | CRISPResso-derived indel outcomes  |
| Known intended edited reference    |  | Defined editing region            |
| WT + intended PE + pegRNA inputs   |  | One WT amplicon, single-copy       |
+------------------------------------+  +------------------------------------+
Availability: [backend capability/version; nuclease pending until qualified]
Imported legacy PE: [resolved mode note, if applicable]
                                                        [Back] [Next]
```

No generic Cas9/base-editor/custom menu that implies unqualified workflows. No silent default when creating an empty new analysis.

## S3 — Target definition (PE variant)

```text
3 / 5 · Precise Edit target             One biological target per workflow
Target name [___________________]
Copies [copy1 ▼] [Add copy/homeolog]     [Per-copy validation status]
WT reference           [multiline sequence input                       ]
Intended PE reference  [multiline sequence input                       ]
pegRNA spacer          [________________]    Extension [_______________]
Nicking guide (optional) [______________]    Scaffold (optional) [______]
[Advanced qualified PE settings ▸]

Backend annotation preview [Valid / Checking / Unavailable / Out of date]
WT          [backend supplied sequence / coordinate track              ]
Intended PE [backend supplied sequence / difference annotations        ]
Guide/edit  [backend supplied intervals; text table available          ]
Copy geometry: [state + reason; target/copy effects explained]
[Coordinate table] [Fit region] [Zoom]                        [Back] [Next]
```

No browser diff/alignment. Switching copies retains each explicit definition. A blocked geometry shows its backend-supported consequences rather than enabling permissive thresholds.

## S3 — Target definition (nuclease variant)

```text
3 / 5 · Indel / Nuclease target        Copies: one [qualified scope]
Target name [________]   Copy ID [________]
WT amplicon [multiline sequence input                                  ]
Window from: ( ) Explicit coordinates   (*) TIGR–Tas · tigr_tas_v1
18-nt target [__________________]       Window [W2 · primary ▼]
[Sensitivity choices W1 / W3 / W4 in advanced section, capability-gated]

Backend preview · illustrative returned values · 0-based inclusive
Target interval 100–117   Orientation: Forward
Amplicon top strand   ...[backend bases and coordinate labels]...
Target                   [------------------]
Cuts                         |       |       104|105 and 112|113
Window W2                    [=======]       104–113 · 10 bases
[Fit target] [−] [+] [Coordinate/annotation table]
Physical cuts, labels and window are returned by Python, never calculated here.
                                                        [Back] [Next]
```

Explicit variant shows a qwc field and backend-selected interval track, with no invented guide/cuts. Reverse labels come from the backend. Palindromic variant: physical locus retained; orientation-specific labels “Unavailable.” Invalid preview never remains styled as validated.

## S4 — Analysis configuration

```text
4 / 5 · Configuration
Read preparation
  (*) Automatic from verified Hi-TOM layout   ( ) Explicit R1/R2 5′ trims
  Resolved [backend R1] / [backend R2]          [Source rule]
Comparisons
  (*) Descriptive summaries only   ( ) Explicit biological contrasts
  [Import contrast specification] [Configure supported contrast]
  A [editor/treatment/dpi] → B [editor/treatment/dpi]   Effect B − A
  Pairing [unpaired / explicit blocks]  BH family [explicit] [Backend validation]
Qualified settings [read-only]
  CRISPResso2 [2.3.4] [lock]     Runtime digest [verified actual identity]
  Mode-specific substitution / insertion / end-exclusion policies [lock]
  [View full scientific configuration]
[PE-family request import only when applicable ▸]             [Back] [Next]
```

No arbitrary additional-parameters textbox. Config flags not mapped to current execution are not advertised as active controls.

## S5 — Review & Run

```text
5 / 5 · Review                             Validated draft [revision/hash]
Samples [n]  Conditions [n]  Biological replicate/block inventory [details]
Mode [Precise Edit / Indel / Nuclease]    Target [id]   Copies [count]
Primary metric [backend label]          Denominator [explicit definition]
Reference/edit or active window [backend preview thumbnail + exact values]
Preparation [resolved rule]  Runtime [version/digest]  Contrasts [none/list]
Output workspace [new backend-visible location]
Warnings / expected unavailable measurements [visible list, not collapsed]
[Edit samples] [Edit target] [View resolved plan]
                                                         [Back] [Run analysis]
Run disabled: [current blockers if any]. Input changes require revalidation.
```

## X1 — Run progress and recovery

```text
Analysis [name]       Running / Verifying / Failed / Completed with limits
Elapsed [backend session time]     Completed nodes [count]   Reused [count]
✓ Source verification            Completed
↻ Demultiplex                    Reused (validated prior stage)
✓ Prepare reads                  Completed
✓ Qualify/route copies OR Single-copy identity check
▶ CRISPResso & metrics           Running · sample [stable ID]
  [expand actual sample-target nodes]
○ Biological summaries/tests     Pending
○ Report                         Pending
○ Final workflow verification    Pending
[View stage logs] [View provenance]                             [Cancel]

Failure: [stage/code] · [short cause]
[Inspect details] [Validate resume] [Preview selective rerun] [New workspace]
```

No faux percentage bar. Cancellation remains “Cancelling” until acknowledged. A native scientific gate is visibly distinct from operational failure.

## R1 — Overview (PE sample variant)

```text
Analysis [name]  Precise Edit  [Verified completion / availability qualifier]
Overview | Samples | Editing | Alleles | QC | Statistics | Provenance
Scope [Experiment / Condition / Sample ▼]   Sample [id]   Population [target]
+-----------------------------------+ +-----------------------------------+
| Exact intended PE      [state]    | | Native PE-reference     [state]   |
| [stored %]   [n exact PE] / [D]   | | [stored %]  [native n] / [native D]|
| D = exact WT + exact PE          | | D = backend-defined native pop.   |
| Assessment: [prepared/other]     | | CRISPResso reference assignment   |
+-----------------------------------+ +-----------------------------------+
Different numerators and denominators; neither is a lower-bound proxy.
Exact WT [count]  Exclusions [count/reasons]  Copy availability [details]
[Biological replicate summary] [Read-flow QC] [Source data]
```

Experiment variant replaces single-sample ratio cards with stored condition means and biological points/n. It never attaches pooled n/D to a mean.

## R1 — Overview (nuclease sample variant)

```text
Indel / Nuclease    Sample [id]   W2 [returned coordinates]   [state]
Indel fraction [stored %]   [indel reads] / [aligned reads]
Exclusive aligned-population inventory
[Unmodified][Sub only][Indel only][Indel + sub][Exceptional, if present]
[Exact counts table; exceptional populations never renormalized away]

Overlapping descriptions — do not sum
Insertion-containing [n/D]   Deletion-containing [n/D]   Substitution [n/D]
Insertion + deletion [n/D]   Any modification [n/D]
[Editing / Net size] [Alleles] [QC]
```

## R2 — Samples

```text
Samples  [Condition filter] [Status filter] [Search] [Columns] [Download source]
Name / ID   Editor / Treatment / dpi   Bio rep   Primary %   n / D   Status
[...]       [...]                     [...]     [...]       [...]   [...]
[...]       [...]                     [...]     —           —       BLOCKED ⓘ
Aligned reads (native population) [optional column with explicit role]
[Page 1 of backend inventory]                              [Selected sample ▸]

Drawer: stable ID, mode, target/copy/policy, stored metrics and reasons
[Editing] [Alleles] [QC] [Source artifact]                               [Close]
```

## R3 — Editing detail

```text
Editing · Sample [id] · Reference [authoritative identity]
[Backend sequence, guide/edit/target, cuts and qwc tracks]
View [Whole amplicon context] [Counted within active qwc]
[Authoritative position series, if supported]
Legend: labelled insertion/deletion/substitution tracks + qwc pattern
[Exact vector table] [Source artifact] [Plot unavailable reason, if absent]

Nuclease: Net indel size within quantification window
Fraction of INDEL-CONTAINING reads
  [negative bins] [0: NET ZERO INDEL] [positive bins]
[Bin count / indel denominator / stored fraction table]
```

## R4 — Alleles

```text
Alleles · Sample [id] · Source [Core child/reference]   [Summary/Sequence]
Rank Class     Reads  Native %Reads  Ins bp  Del bp  Sub  Net Δ  Reference
[...] [...]    [...]  [...]          [...]   [...]   [...] [...] [...]
20 of [N] rows; complete authoritative table preserved. [Page] [Download]

Selected original row [artifact hash + row identity]
Reference  [authoritative aligned string]
Read       [authoritative aligned string]
Events     [backend annotations or explicit unavailable]
Legend: bold/underline substitution | '-' deletion | outlined insertion
[Coordinates/window/cut overlay when qualified] [Text details]
```

## R5 — QC

```text
QC · Sample [id]    [Target / Confident copy / Native child population]
Raw pairs → Expected demux assigned → Prepared pairs
               ↘ barcode terminal categories + matrix
PE target:       ├→ Exact assessment → Exact WT + PE / excluded
                 ├→ Native Core → Preprocessed → Aligned / Unaligned
                 └→ Copy routing → confident cohorts / quarantine
Nuclease:        → Single-copy identity → Core → Aligned / Unaligned
                                             → ordinary / exceptional classes
[Backend-selected relationships; no forced parallel-population funnel]
Counts ledger · Unit · Denominator · Attrition reason · Source
[Native guardrails: separately attributed] [Detailed data]
```

## R6 — Statistics

```text
Statistics · Series [target/metric/population/copy/policy]   [Family]
Biological samples [equal-sized points]   Mean [stored marker]
Range [stored min–max, descriptive]       Expected / reportable n [counts]
Contrast       A → B        B − A       p        q        Used n    Status
[...]          [...]        [...]       [...]    [...]    [...]     [...]
[Explicit paired blocks and exclusions] [Permutation details] [Source JSON]
If no contrasts: Descriptive summaries only — no statistical tests requested.
```

## R7 — Provenance & Native output

```text
Provenance · Verified lineage
PEAnalyzer [version / code hash]   Mode/contracts [identities]
CRISPResso [2.3.4 / actual runtime digest]  Target/profile/window [values]
Inputs [hash inventory]  Stages [executed/reused]  Report [hash inventory]
[Full scientific configuration] [Resolved args] [Sessions] [Download manifests]

PEAnalyzer output [Open verified report] [Tables] [Figures] [Exact source JSON]
Native CRISPResso · Child [sample / role / reference]
[Browse inventoried artifacts] [Download preserved bundle]
[Open native report: disabled if absent]
“Native HTML was not generated; machine-readable outputs are preserved.”
If available: Open in isolated native viewer, outside application privileges.
```
