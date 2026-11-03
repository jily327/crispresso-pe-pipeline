# PEAnalyzer 1.0 desktop use

The desktop release adds Light/Dark themes, a bounded analysis library, optional
Windows Explorer reveal, and a top-level precise-edit summary workbook. Scientific
calculations and the M11B/M11C supervision, recovery and authentication rules are
unchanged.

## Light and Dark

Use **Theme** in the application header in Setup, Run, Recovery or Results.
First use always selects Light, regardless of the operating system preference.
An explicit choice is stored in this browser's local storage. If browser storage
is disabled the choice lasts for the current page. Generated scientific SVG/HTML
reports retain their stored appearance and bytes.

## Discover previous analyses

Configure one or more explicit directories on the local launcher:

```sh
peanalyzer-viewer --workspace-library-root "$HOME/PEAnalyzer-analyses"
```

Use **Refresh library** in Open Existing Analysis after another run appears.
Discovery never runs a scientific stage or writes into a workspace. It uses at
most four directory levels, 5,000 directories, 20,000 directory entries and 500
workspace candidates per refresh, with 2 MiB marker limits. Narrow your configured
roots if the UI reports a discovery limit. Symlink directories/markers and special
files are excluded. Overlapping roots are deduplicated. The browser supplies no
filesystem paths to discovery or Explorer.

Labels use stored workflow software provenance, not version text in folder names.
**Detected — verification required** is catalogue metadata, not a scientific
verification claim. Open and verify still runs the full existing verifier.
Malformed or unsupported contracts stay visible as incompatible. If full Open
fails, the verifier's error remains visible and the catalogue label changes to
incompatible. Missing completion markers are labelled **Incomplete — use Recovery**;
register these explicitly with `--recover-workspace` to inspect recovery.
Discovery does not automatically authorize recovery or migrate schemas.

Old analyses are opened read-only. No workbook is added merely by viewing a
historical analysis, including through Recovery's Open Results action. Keep source
inputs and their recorded paths available for full verification.

## One permanent Windows launcher

Copy `desktop/PEAnalyzer.bat` to Windows once. It starts Docker Desktop if needed,
waits up to three minutes for Docker in Ubuntu-24.04, and calls the stable WSL entry
`~/peanalyzer-current/run-oneclick.sh`. It contains no release version.

Install each release into its own WSL directory, for example:

```sh
mkdir -p "$HOME/peanalyzer1.0.0"
python3 -m venv "$HOME/peanalyzer1.0.0/venv"
"$HOME/peanalyzer1.0.0/venv/bin/pip" install 'crispresso-pe-pipeline[gui]==1.0.0'
cp desktop/run-oneclick.sh "$HOME/peanalyzer1.0.0/run-oneclick.sh"
chmod +x "$HOME/peanalyzer1.0.0/run-oneclick.sh"
ln -sfn "$HOME/peanalyzer1.0.0" "$HOME/peanalyzer-current"
```

Install from the qualified release wheel instead of the package index when that
wheel is the distributed artifact. The stable entry must be a symlink (not an
existing ordinary directory). Point it at the next installed release to update;
the permanent BAT remains unchanged. Keep the previous release for rollback.

The launcher reads the installed distribution version. New output parents are
`$HOME/PEAnalyzer-analyses/v<installed-version>/`; discovery scans the common parent.
Set `PEANALYZER_LIBRARY_ROOT` in the WSL login environment to choose another stable
library location. Set `PEANALYZER_CRISPRESSO` to the existing qualified executable
wrapper, or install it at the release's `bin/CRISPResso`. The launcher checks Docker
availability, but does not replace the backend's pinned CRISPResso2 2.3.4 runtime
checks. Open the local URL printed by the application. Startup errors stay visible
in the BAT console. Extra CLI arguments may be passed to `run-oneclick.sh`.

## Completed analysis convenience

A newly completed GUI job attempts Explorer reveal once on the server, after
verified publication and summary finalization. On WSL this uses `wslpath -w` and
`explorer.exe /select,` via argument arrays, without a shell. Explorer opens the
parent folder with the analysis selected. Reloading a page and opening an older
analysis do not trigger automatic reveal. **Open output folder** retries manually
for any currently verified completed workspace. Unsupported desktops or Explorer
errors show a nonfatal message and never change COMPLETED or scientific output.

## PEAnalyzer_Summary.xlsx

New GUI precise-edit analyses receive `PEAnalyzer_Summary.xlsx` at the workspace
root before registration in the immutable viewer snapshot. Successful recovery of
an unpublished current-release analysis also finalizes this presentation file.
An existing summary is checked against verified metrics, never silently overwritten.
CLI scientific stages are unchanged; this is a GUI finalization artifact.

The Summary sheet has exactly these columns:

| Column | Meaning |
| --- | --- |
| Sample name | Authoritative sample name, stored as literal text |
| Barcode | Authoritative barcode ID |
| CRISPResso edit % | `target_crispresso_native_pe`: Prime-edited-reference assigned reads / authoritative aligned reads; **NOT Modified%** |
| CRISPResso reads/reads | Exact stored numerator / denominator |
| Precise edit % | `total_precise_pe`: exact intended PE / (exact WT + exact intended PE), under the existing observability/reconstruction qualification |
| Precise reads/reads | Exact stored numerator / denominator |

Percentages are stored backend fractions formatted `0.00%`. Counts remain exact
text, including integers beyond Excel's numeric precision. BLOCKED,
NOT_ASSESSABLE or missing observations show **Not available**, never invented zeros.
Copy-routed diagnostic metrics are not used. Original sample CSV order is used
when available with verified input hashes; otherwise rows use deterministic barcode
ID order. The Definitions sheet records metric identifiers, meanings, package
version, workspace/target and source hashes. No frontend or FASTQ recalculation is
involved. A temporary workbook is finalized before atomic, exclusive publication.
A failed export prevents viewer publication without rewriting scientific outputs.

Back up the entire analysis and source inputs. Backup is not supported workspace
relocation: absolute lineage and recovery authentication bind paths and, for
recovery, host/account/root identity. Never move old analyses merely to place them
under a newer version directory. Configure additional library roots instead.
