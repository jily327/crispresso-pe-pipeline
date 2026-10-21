# Milestone 3: external backend validation

**ROUTING GATE: FAIL.** CRISPRessoPooled 2.3.4 routed all 310 informative
synthetic reads correctly, but also sent all 40 deliberately non-informative or
equal-score reads to individual copy analyses. The BAM exposes tied scores; the
default Pooled handoff does not quarantine them. Execution success is therefore
not authorization for biological copy quantification. No M4 metrics are enabled.

This milestone starts at `ae7e7f3e1f9144ea2092d9a6201a4d137a024214`, which contains
M2.1 `e195fd9b734c7f016ca686fb5f8fa76ede097a68`. M2 production modules and their
publication format are unchanged. New APIs implement verification, preparation,
external diagnostic execution and synthetic-only routing audit.

## Completion boundary and preparation

`peanalyzer.demux_verify.verify_demux_output(path)` returns a `VerifiedDemuxRun`
only after checking schema 2, completed publication state, all eight required
reconciliation checks, terminal/sample sums, exact authoritative inventory,
paths, sizes, SHA-256, sample/mate mappings, barcode identities and matrix sums.
Staging paths and symlinks to authoritative files are rejected. Every mate is
decompressed with the existing four-line FASTQ parser, independently counted and
checked for synchronized IDs. Zero-read samples are valid. Hashing compressed
bytes is a separate streaming pass; the verifier retains no reads in memory.
The summary is hashed before and after verification. This is integrity checking,
not cryptographic authentication against coordinated rewriting of all metadata.
Archived results must not be concurrently modified.

The adversarial suite covers flipped bytes, appended gzip members, truncation,
deleted files, unequal mate counts, wrong IDs, status/check changes, missing
checks, altered matrices, incorrect sample mapping, size/hash mismatches,
unsupported schema, traversal inventory, extra FASTQs and completed-looking
staging directories. Recount tests refresh hashes after tampering so rejection
cannot depend only on checksum mismatch. Both appended mates with unchanged
claimed counts are independently rejected.

`peanalyzer.analysis_fastq.prepare_analysis_fastqs(demux_root, output, config)`
always calls the verifier itself. It publishes a separate, new directory:

```text
demux/01_demux_QC/                 immutable M2 archive
demux/02_demultiplexed_fastq/      immutable M2 archive
analysis/analysis_manifest.json
analysis/03_analysis_fastq/<barcode_id>_R{1,2}.analysis.fastq.gz
backend/execution.json            execution status, not routing approval
backend/output/CRISPRessoPooled_on_diagnostic/
05_routing_QC/                    synthetic audit only
```

For an untrimmed `qi_hitom_v1` archive, the trim is derived from its recorded
extraction offset + barcode length + bridge length: 0 + 9 + 18 = **27 per mate**.
Forward bridge is `GGAGTGAGTACGGTGTGC`; reverse is `GAGTTGGATGCTGGATGG`.
`PreparationConfig(r1_analysis_trim_5p=0, r2_analysis_trim_5p=0)` explicitly
disables trimming. Other layouts require both explicit nonnegative values.
No 27-nt biological constant is embedded in preparation logic.

Header and plus-line bytes remain intact; identical positions are removed from
sequence and quality. Pair order and IDs are preserved, and no pair is silently
dropped. Reads of length <= trim fail (equality would produce an invalid empty
read). Written pairs are parsed again and reconciled against the verified count.
Source hashes are rechecked before staged publication. Output inside the archive,
including via a symlinked parent, is rejected. Tests cover alternate trims,
trim=0, empty samples, too-short reads, source preservation and spaces in paths.

```python
from pathlib import Path
from peanalyzer.demux_verify import verify_demux_output
from peanalyzer.analysis_fastq import prepare_analysis_fastqs

verified = verify_demux_output(Path('/data/completed-demux'))
manifest = prepare_analysis_fastqs(verified.root, Path('/data/new-analysis'))
```

A read-only local check of the existing M2.1 EV-only result independently
recounted **85,878 assigned pairs across 12 samples**. No real reads were used for
M3 routing or editing analysis, copied into the repository, or committed.

## External runtime and input interface

The package has no CRISPResso Python dependency and imports no CRISPResso
internals. `resolve_executable()` resolves an executable and probes `--version`;
both Core and Pooled must report exactly **2.3.4**. Other versions require a new
qualification experiment. Unit tests need neither the tool nor network access.

Actual execution used the official `pinellolab/crispresso2:v2.3.4` image, pinned:

```text
pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c
CRISPResso 2.3.4
CRISPRessoPooled 2.3.4
bowtie2-align-s 2.5.5
samtools 1.23.1
fastp 1.3.3
```

The tag without `v` does not exist. Environment-local executable shims invoked
Docker with `--network none`, the calling UID/GID, identical `/workspace` and
`/tmp` bind mounts, the current directory, and `--entrypoint` for each tool.
The application only sees executable paths. This is a validation setup, not a
general Docker/WSL adapter. Native/Conda executables use the same API; Windows
packaging and WSL transport remain future work. Full version probes and runtime
identity are in [the evidence directory](validation/m3/README.md).

The exact TSV headers were checked against installed Pooled 2.3.4 and upstream
[v2.3.4 source](https://github.com/pinellolab/CRISPResso2/blob/v2.3.4/CRISPResso2/CRISPRessoPooledCORE.py).
Installed Pooled source SHA-256 is
`95d7843646636f6a49aae12a041f0dcce059ad40035a90d715a1adb9b4d71b68`.
No source is vendored. `FIELDS` in `backend/pooled.py` defines the ordered mapping:

| Header | Target field |
| --- | --- |
| `amplicon_name` | `amplicon_id` (`target_name__copy_name`) |
| `amplicon_seq` | `wt_sequence` |
| `prime_editing_pegRNA_spacer_seq` | `pegRNA_spacer` |
| `prime_editing_nicking_guide_seq` | `nicking_guide` |
| `prime_editing_pegRNA_extension_seq` | `pegRNA_extension` |
| `prime_editing_pegRNA_scaffold_seq` | `pegRNA_scaffold` |
| `prime_editing_override_prime_edited_ref_seq` | `prime_edited_sequence` |
| `prime_editing_pegRNA_scaffold_min_match_length` | same name |
| `quantification_window_coordinates` | same name |
| `quantification_window_size` | same name |
| `quantification_window_center` | same name |

Rows are sorted by amplicon ID, tab-delimited, with `NA` for absent values.
Any number of copy rows is supported; the two-copy fixture imposes no production
copy-number limit. WT identities must be distinct, including reverse complements;
the extension's reverse complement must be present in the intended PE reference.
This conservative extension rule retains the existing sequence convention and
does not establish biological pegRNA validity.

`pegRNA_spacer` means the **actual experimental guide**, repeated unchanged on
copy rows when shared. It is not an analysis override. The explicit PE reference
column supplies the intended haplotype; it does not override guide checks.
The artifact's cleaned upstream names (`SYN_copy1`) are mapped back using Pooled
JSON display-name mappings (`SYN__copy1`), never inferred by string replacement.

The deterministic diagnostic argv is:

```sh
CRISPRessoPooled -r1 input_R1.fastq.gz -r2 input_R2.fastq.gz \
  -f amplicons.tsv -o output --name diagnostic --crispresso_command CRISPResso \
  --n_processes 1 --min_reads_to_use_region 0 --write_detailed_allele_table \
  --suppress_report --suppress_plots --keep_intermediate
```

Our subprocess boundary uses argv arrays and never `shell=True`. Upstream Pooled
internally constructs shell commands, so inputs are copied into a private,
shell-safe scratch path with fixed relative names. The child executable is
quoted for the upstream shell. Caller input/output paths may contain spaces;
the formal integration tests exercise this. Unsafe scratch paths fail clearly.
`child_core_command` may explicitly name a command inside an external runtime;
the caller is responsible for ensuring it is the probed Core executable.

`execution.json` records software version, Git commit/dirty state, executable and
version probes, exact argv/cwd/output, input hashes, TSV/configuration hashes,
timestamps, return code and failure status. stdout/stderr and upstream child
commands are retained. Scratch is copied to the diagnostic output, then removed;
absolute scratch references in upstream logs describe the original invocation.
Their relative paths locate the retained files under `backend/`.

Missing executables, version mismatches, nonzero exit, missing/incomplete JSON,
reported child failures and incompatible targets fail explicitly. Failed runs
retain a `status: failed` diagnostic manifest and raise `BackendError`. A
completed execution manifest only means that execution completed. There is no
production routing/quantification continuation in M3.

## Synthetic ground truth and observed routing

Full WT/PE sequences and guide fields are committed in
[baseline/synthetic_design.json](validation/m3/baseline/synthetic_design.json).
They are artificial, deterministic (seed 20261021), and are not unpublished ALS
sequences. Both amplicons are **240 bp**, with four diagnostic SNPs. Coordinates
below are **zero-based**; guide intervals are half-open.

| Position | copy1 WT | copy2 WT |
| --- | --- | --- |
| 40 | A | C |
| 80 | C | G |
| 165 | T | A |
| 205 | C | G |

The intended edit is **122 G→T** in both copies. The experimental spacer is the
copy1 sequence at `[95,115)`; the extension is the reverse complement of its
intended PE sequence at `[105,145)`. No nicking guide or scaffold is supplied.
The design hash is
`5d6cb8f1379b22245e4dc203a8939ae9e83d9bdfdfb3370e8f7ceacebdd2ec3a`.

Full-fragment paired reads cover 150 nt from each end (60-nt overlap for WT/PE).
A deletion at 150 creates 239-nt fragments. Partial reads cover only `[115,155)`:
40 nt without diagnostic sites. Both mates receive the verified 27-nt Hi-TOM
prefix, which is removed only after M2 publication and verification. IDs and a
separate truth CSV encode origin before any backend execution.

| Read class | copy1 origin | copy2 origin | No unique origin |
| --- | ---: | ---: | ---: |
| WT | 80 | 50 | 0 |
| precise PE | 60 | 40 | 0 |
| PE + extra substitution at 55 | 12 | 8 | 0 |
| unintended 1-nt deletion at 150 | 12 | 8 | 0 |
| ordinary sequencing substitution at 55 | 12 | 8 | 0 |
| sequencing substitution at diagnostic 40 | 12 | 8 | 0 |
| missing diagnostic coverage | 10 | 10 | 0 |
| equal-score mosaic, two alleles from each copy | 0 | 0 | 20 |

All **350 raw pairs** were assigned to sample 1B by strict M2 matching, verified,
prepared and merged for Pooled. The first six classes contain 310 informative
reads; the remaining 40 deliberately cannot support a unique origin.

| Ground truth | Routed copy1 | Routed copy2 | Unassigned | Multiple |
| --- | ---: | ---: | ---: | ---: |
| Informative copy1 | 188 | 0 | 0 | 0 |
| Informative copy2 | 0 | 122 | 0 | 0 |
| Non-informative/equal-score | 23 | 17 | 0 | 0 |
| Total | 211 | 139 | 0 | 0 |

There are **zero cross-routed informative read IDs**. All 40 non-informative
reads have `AS == XS` in the actual BAM and nevertheless entered copy FASTQs.
Missing-coverage reads split 12/8; mosaics split 11/9. This split is an observed
tie-breaking outcome, not biological evidence or an asserted universal ratio.
They are neither excluded nor duplicated in this run. No ambiguity-rescue flag
was enabled. `explicit_backend_ambiguous_read_count` is null, not zero, because
Pooled provides no qualifying cross-copy ambiguity category here. The audit
separately exposes 40 score ties; routine copy tables alone conceal their status.

Per-read evidence comes from `CRISPResso_AMPLICONS_ALIGNED.bam`, extracted using
`samtools view`, and IDs in `AMPL_<cleaned_run_name>.fastq.gz`. The audit requires
the BAM routing and copy FASTQ handoff to agree exactly. Pooled JSON supplies the
name/folder mapping. Each child's `CRISPResso2_info.json` confirms its own distinct
`Reference` and `Prime-edited` sequences, and the ZIP allele table confirms
**60 copy1 and 40 copy2 exact synthetic PE reads assigned to their PE reference**.
This is a reference smoke test; it is not a PE-efficiency definition, and not all
Pooled-routed reads necessarily survive Core's subsequent alignment filters.
No HTML parsing or private CRISPResso decoder is used.

## Faithful guide-mismatch experiment

A separate design adds a fifth copy2 SNP at position **100 C→G**, inside the
experimental spacer and outside the extension segment. The actual copy1 spacer
and extension are unchanged on both rows. Copy2 still has its explicit intended
PE reference. Its complete design is in
[guide_mismatch/synthetic_design.json](validation/m3/guide_mismatch/synthetic_design.json).

Actual Pooled 2.3.4 execution rejects this setup: copy1 completes, copy2 Core
exits **6**, and Pooled exits **255**. The retained child log says:

```text
ERROR: The given prime editing pegRNA spacer is not found in the reference sequence
```

`preflight_guides()` now raises `PE_GUIDE_REFERENCE_MISMATCH_UNSUPPORTED` if the
actual spacer and its reverse complement are both absent from a copy's WT.
Normal execution checks this before launching a process. The explicitly named
`diagnostic_test_unsupported_guide=True` switch only permits re-running the
faithful rejected configuration for the integration test. It changes no guide,
backend sequence check or biological metadata. The resulting backend manifest
remains failed, and the diagnostic result prohibits downstream analysis. No
Flexiguides or override rescue was tested or adopted.

This establishes an executable limitation, not whether the real biological guide
can edit a mismatched homeolog. Actual guide identity, genotype, WT/PE haplotypes,
copy number, sequencing coverage and acceptable ambiguity exclusions still need
experiment-specific confirmation.

## Reproduction and scope after failure

Normal suite, without CRISPResso:

```sh
python -m pytest -q -m 'not crispresso_integration'
python -m build --no-isolation
```

Opt-in real backend suite with Core/Pooled 2.3.4, Bowtie2, fastp and samtools:

```sh
M3_INTEGRATION=1 python -m pytest -q -m crispresso_integration
```

Optional `M3_CORE_EXECUTABLE`, `M3_POOLED_EXECUTABLE`, `M3_SAMTOOLS_EXECUTABLE`,
`M3_CHILD_CORE_COMMAND` select the executable boundary. `M3_RESULTS_DIR` selects
an external output root whose `baseline` and `guide_mismatch` children must not
already exist. Otherwise pytest uses a new temporary directory. The real tests
assert the observed unsafe/rejected behavior; four passing regression tests do
not mean that the scientific routing gate passed.

The smallest next routing design is an explicit evidence gate before per-copy
editing: compare each read's support across every copy's WT and intended-PE
references; keep routing separate from editing state; require covered diagnostic
evidence and a unique defensible copy assignment; quarantine score ties, missing
diagnostics and conflicting/chimeric evidence with per-read reasons. Using only
the current BAM's primary hit or an arbitrary MAPQ cutoff is insufficient. Reuse
a standard aligner and retain competing alignments; do not write a replacement
aligner here. Validate WT/PE routing bias, edited diagnostic sites, unequal
coverage, repeats and reference-order sensitivity before qualification.

Milestone 4 should remain blocked on that focused routing follow-up and an
explicitly reviewed strategy for mismatched experimental guides. Only after a
passing routing gate should M4 parse copy-specific editing outputs and validate
the intended full-amplicon metric and denominators. This milestone implements
no final PE metric, aggregation, statistics, biological report or GUI.
