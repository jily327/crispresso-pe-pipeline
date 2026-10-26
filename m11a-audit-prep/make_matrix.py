from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent
# Each line is one independently assertable candidate audit case, not a claimed test result.
groups={
'Z — Zero execution':'''Open New Analysis with Core absent || Setup loads; no executable/version probe, subprocess or runtime-qualified claim || BLOCKING
Validate complete raw PE draft || Strict metadata/file validation only; all scientific executor traps remain zero || BLOCKING
Validate complete nuclease draft || Pure NucleaseTarget/window/expected-argument helpers allowed; no Core || BLOCKING
Preview PE insertion/deletion || No geometry-triggered route_pair trials; honest annotation-unavailable state if no safe helper || BLOCKING
Preview M2 analyze draft || Read-only archive verification allowed; no preparation, route, metrics, locks or sessions || BLOCKING
Repeat preview many times || No background execution, demux dry-run or automatic native report creation || BLOCKING
Trap captured aliases/default arguments || Patch bindings and trace original function code; swallowed exceptions still count as forbidden attempts || BLOCKING
Trap subprocess from provenance/capabilities || Request-scoped git/version probes fail the zero-subprocess rule; bootstrap provenance must be distinguished and documented || BLOCKING
Attempt resume/force/submit via forged setup request || Unsupported operation rejected; no recovery or workflow mutation || BLOCKING
Check expected versus observed runtime fields || Expected 2.3.4/profile/digest may be displayed; actual installed version/resolved Core args cannot be certified without execution || MAJOR''',
'R — Draft revision races':'''A valid validation arrives after a newer invalid edit || Immediately invalidate current validation/Review; late valid A never enables it || BLOCKING
A invalid validation arrives after a newer valid edit || Late A cannot overwrite new errors or new validation status || MAJOR
Preview PE A pending then switch to nuclease || A is ignored; no PE geometry or identity appears under nuclease || BLOCKING
Review visible then target changes || Plan unavailable synchronously on edit, before debounce/network reply || BLOCKING
Sample identity changed after validation || Revision advances; old source mapping/plan cannot be current || BLOCKING
File bytes change with same path/size/mtime || Content hash changes or source-change failure; stat-only identity is insufficient || BLOCKING
Two preview responses return in reverse order || Only response matching current draft ID/revision and submitted content identity is accepted || BLOCKING
Close draft and create a new one before old response returns || A response from old draft ID cannot attach to new draft even when revision numbers match || BLOCKING
Abort request but server completes anyway || Abort is not the correctness mechanism; stale response checks still hold || BLOCKING
Repeated identical draft requests || Same scientific identity; request IDs/revisions may differ without changing science digest || MAJOR''',
'M — Mode contamination':'''PE→nuclease→PE || Preserve or discard inactive data deliberately; only active-mode payload affects preview || BLOCKING
Nuclease→PE→nuclease || Restored active window/profile must be explicitly revalidated, never restored as current validity || BLOCKING
Forge nuclease request carrying PE references/guides || Active nuclease payload rejects PE extras; explicitly separate saved inactive draft data may be retained but never enters identity || BLOCKING
Forge PE request carrying TIGR fields || Inactive TIGR/qwc selection cannot change PE target, preview or plan || BLOCKING
Switch TIGR→explicit window || Clear active profile/target/window binding; backend rejects both selectors submitted as active || BLOCKING
Switch explicit→TIGR || Old explicit qwc cannot override backend-selected W1–W4 || BLOCKING
Switch multicopy PE→single-copy nuclease || No silent merge or leftover copies; explicitly valid single-copy target or blocking error || MAJOR
Edit inactive saved mode fields || Active scientific identity unchanged; switching back requires fresh validation || MAJOR''',
'S — Samples and input source':'''Missing R1 || BLOCKING INVALID for raw mode; no valid plan || BLOCKING
Missing R2 || BLOCKING INVALID for raw mode; no valid plan || BLOCKING
R1 equals R2 or same inode/hardlink || BLOCKING INVALID; identity checked before execution, not by calling demultiplex || BLOCKING
Nonexistent input || BLOCKING INVALID; do not manufacture file hash or accept basename alone || BLOCKING
Swapped mates with /1 /2 or CASAVA annotations || BLOCKING INVALID after read-only paired_fastq check; wrong mate annotation || MAJOR
Swapped unmarked mates || VALID WITH WARNING when otherwise synchronized; orientation cannot be inferred from filenames; explicit role confirmation || MINOR
Malformed CSV header/row/barcode DNA/duplicate column || BLOCKING INVALID with row/column evidence from loader || MAJOR
Duplicate forward/reverse pair || BLOCKING INVALID; shared one-sided barcode alone remains allowed || MAJOR
Duplicate stable barcode_id, including casefold collision || BLOCKING INVALID; do not silently sanitize/renumber || MAJOR
Duplicate biological display sample_name || BLOCKING INVALID under current load_samples, despite being a display-facing field || MAJOR
Repeated editor/treatment/dpi condition with distinct biological replicates || VALID; presentation may group it; must not merge biological rows || MAJOR
Repeated biological_replicate within condition and target || BLOCKING INVALID for end-to-end readiness; metadata loader accepts but M5 later rejects; do not run M5 to check it || MAJOR
Blank editor/treatment/dpi || BLOCKING INVALID; no implicit control dpi or editor default || MAJOR
Extra valid expected sample-sheet row absent from reads || VALID WITH WARNING or explicitly unassessed assignment; no invented assigned counts; do not auto-drop the sample || MAJOR
Unused authoritative barcode catalog entry || VALID, normally PRESENTATION-ONLY; full catalog is deliberately broader than expected sample pairs || MINOR
Unknown catalog ID or conflicting barcode sequence || BLOCKING INVALID; no fuzzy correction/rescue of metadata || MAJOR
FASTQ expected-barcode mismatch without running demux || VALID WITH WARNING that assignment is unassessed; no Ready badge claiming barcode coverage was proved || MAJOR
Read length at/below preparation trim || BLOCKING INVALID once established for the relevant prepared population; length==trim produces empty reads; no preparation execution || MAJOR
Valid verified M2 archive || VALID input source analyze; source files remain immutable; raw R1/R2 inactive || MAJOR
M2 read length at/below requested trim || BLOCKING INVALID for that archived sample; read-only inspection only || MAJOR
Mutated source after validation || BLOCKING INVALID until refreshed identity and current validation; no stale plan reuse || BLOCKING
Symlink or source path outside approved roots || BLOCKING INVALID; opaque input handles cannot be forged into arbitrary paths || BLOCKING
Same basename inputs from different directories || PRESENTATION-ONLY disambiguation; IDs/hashes map each source correctly || MAJOR
Paired-end sequencing versus paired statistical design || Independent controls; paired=true requires block_id, not inferred from R1/R2 || MAJOR''',
'P — PE target':'''Simple SNP || Target accepts; pure geometry substitution annotation must equal PE_SNP_ANNOTATION golden || MAJOR
Multiple substitutions || Model accepts; exact supplied intended reference remains authoritative || MAJOR
Insertion || Model accepts; do not execute experimental routing qualification to preview || BLOCKING
Deletion || Model accepts; no arbitrary indel-length cutoff or frontend reconstruction || BLOCKING
Mixed multiple intended differences || Model accepts; preserve exact intended product; missing safe annotation is explicit || MAJOR
Invalid DNA ambiguity/gap/internal space || BLOCKING INVALID; only A/C/G/T reference alphabet; RNA U normalization is guide-specific || MAJOR
WT identical to intended || BLOCKING INVALID; no intentional edit exists under Target contract || MAJOR
Missing spacer || BLOCKING INVALID even though other fields look complete || MAJOR
Malformed spacer || BLOCKING INVALID for alphabet; a well-formed absent spacer is a separate preflight issue || MAJOR
Missing extension || BLOCKING INVALID; no inferred PBS/RTT/extension || MAJOR
Missing nicking guide || VALID under Target; do not invent a requirement or a guide || MAJOR
Reverse-only spacer || Model accepts but qualified pure preflight rejects PE_GUIDE_ORIENTATION_UNSUPPORTED; do not reverse supplied experiment to rescue || MAJOR
Wrong shared guide/extension across copies || Backend geometry rejects inconsistent experiment; no silent per-copy guide synthesis || MAJOR
Duplicate copy, casefold identity, duplicate/reverse-complement WT || BLOCKING INVALID at the appropriate collection/geometry gate || MAJOR
Homeolog ambiguity with insufficient pair diagnostics || Schema-valid does not mean copy routing SAFE; display backend-supported unresolved/blocked state, never claim eligibility || MAJOR
PE qwc sentinel 0 || Legacy PE model accepts it; not a nuclease explicit coordinate; scope/qualification caveat must remain visible || MAJOR''',
'N — Nuclease target':'''Normal explicit 10-20 || Valid, zero-based inclusive; expected intervals [[10,20]] || MAJOR
Literal explicit sentinel 0 || BLOCKING INVALID with NUCLEASE_WINDOW_REQUIRED || BLOCKING
Real explicit 0-0 || Valid one-base coordinate, no false sentinel rejection || MAJOR
Reversed 20-10 || BLOCKING INVALID || MAJOR
Out of range 59-60 on 60nt WT || BLOCKING INVALID || MAJOR
Ordered disjoint multi-interval 1-3_8-10 || Valid; not a single-window-only GUI rule || MAJOR
Overlapping/unordered intervals || BLOCKING INVALID, no frontend sorting/repair || MAJOR
Boundary 0-59 or 59-59 || Valid within 60nt WT; no PE end-exclusion rule applied || MAJOR
TIGR forward target || Exact golden physical locus, forward labels and intervals || MAJOR
TIGR reverse target || Same physical-locus coordinate rules; target-oriented labels swap; no frontend reverse math || MAJOR
TIGR palindrome || One physical locus; orientation palindromic, directional labels and between-cut target-oriented sequence null || MAJOR
TIGR absent target || BLOCKING INVALID, TIGR_TARGET_MISSING || MAJOR
TIGR multiple physical matches || BLOCKING INVALID, TIGR_TARGET_NOT_UNIQUE || MAJOR
TIGR W1/W2/W3/W4 and omitted W2 || All four advertised choices match independent goldens; W2 only default || MAJOR
TIGR length not 18 or non-DNA target || BLOCKING INVALID; U not accepted for nuclease DNA || MAJOR
TIGR W4 clipped at left/right edge || Match clipped golden intervals exactly, not negative/out-of-bounds coordinates || MAJOR
Multiple nuclease copies or PE tolerance policies || Production scope unsupported; schema/model validity cannot be promoted to a supported plan || MAJOR''',
'I — Deterministic identity':'''Same normalized scientific draft twice || Identical canonical scientific payload/digest; response revision/request metadata separate || MAJOR
Change UI step/filter/selection/zoom/sort || Scientific identity unchanged || MAJOR
Change input bytes preserving name/path/size || Scientific source identity changes or mutation invalidates || MAJOR
Change barcode assignment || Input/scientific identity changes, stable sample join remains barcode_id || MAJOR
Change WT/intended/copy/target identity || Active target scientific identity changes || MAJOR
Change TIGR window or explicit qwc || Active normalized scientific identity changes || MAJOR
Omitted W2 versus explicit W2, 010-020 versus 10-20 || Equivalent normalized nuclease identity; exact source-file identity may still differ || MAJOR
Reorder semantically equivalent sample/copy rows || Sorted DAG semantics stable; source byte hashes may change and must not be erased || MAJOR
Change report title/output destination || Distinguish report/execution identity from science-only subset; do not falsely require full M7 Plan hash invariance || MAJOR
Change sample_name/editor/treatment/dpi/biological replicate || Real metadata is not presentation-only; current conservative lineage/statistical grouping changes || MAJOR''',
'O — Destination safety':'''Nonexistent destination || VALID if authorized/separate with suitable existing ancestor; preview creates no path or parent || BLOCKING
Existing empty directory || BLOCKING INVALID for a new run, because execute_workflow rejects any existing root || MAJOR
Existing unrelated nonempty directory || BLOCKING INVALID; no adoption/overwrite/deletion || BLOCKING
Existing PEAnalyzer workspace || BLOCKING INVALID as a new output; may offer Open Existing, never implicit resume/force || BLOCKING
Symlink destination or ancestor || BLOCKING INVALID; no follow-through creation || BLOCKING
Traversal/absolute child/backslash attack || BLOCKING INVALID at approved-root/path gate; no_symlinks alone is not traversal rejection || BLOCKING
Read-only parent || BLOCKING INVALID when demonstrable; use non-root OS oracle; no create/delete writability probe in science destination || MAJOR
Destination equals or contains inputs/source directory || BLOCKING INVALID; no output/input overlap, no archive mutation || BLOCKING''',
'V — Review fidelity':'''Mode/sample count/stable IDs || Render exact backend preview values; count biological rows, not files or reads || MAJOR
Target and PE copy count || Group one target with its real copies, not one target per row || MAJOR
Nuclease profile/window/qwc/configuration || Render backend-normalized fields/expected profile; no generic hardcoded W2 || MAJOR
Scientific identity and validation revision || Show only latest validated payload and matching revision; never derive a second JS identity || BLOCKING
Stage graph || Match backend nodes/dependencies; nuclease routing slot labelled single-copy identity || MAJOR
Marked backend response oracle || Inject distinctive valid preview fields/coordinates/IDs; Review uses supplied values, not independently reconstructed geometry || MAJOR''',
'U — Hidden errors and accessibility':'''Invalid sample filtered out || Global blocking summary remains; error action clears/reveals filter and focuses correct row || MINOR
Invalid row below viewport/page || Error navigation reveals the row and usable focused field, not an offscreen node || MINOR
Invalid field on another step || Review blocked; summary takes user to that step and field without deleting draft || MINOR
Several invalid fields || Stable useful first error, remaining errors discoverable; focus not trapped || MINOR
Press Review immediately after edit || Invalidation synchronous; cannot outrun debounce or reuse cached prior validity || BLOCKING''',
'G — Small M10 regression boundary':'''Open existing PE fixture || Existing full-open verification and viewer remain usable; setup executors still unavailable || MAJOR
Open existing nuclease fixture/Overview || Stored data and mode remain unchanged || MAJOR
Navigate five result tabs || Existing snapshot-based navigation retained; no broad re-audit || MINOR
Mutate one opened artifact || Existing changed-workspace failure and hide-results behavior retained || BLOCKING
Edit setup draft while viewer has an open workspace || Draft mutations cannot change cached result, source handles or selected workspace identity || BLOCKING
Switch New Analysis↔Open Existing repeatedly || State namespaces stay separate; stale preview cannot be shown as existing scientific result || BLOCKING''',
'K — Packaging and offline':'''Record stable candidate HEAD || No final PASS until implementer declares stability; record exact parent/diff/version || INFO
Validate production source/asset identity || Existing build gate remains active after setup frontend changes || MAJOR
Build clean checkout wheel || Includes setup and reader production assets; no editable-source leakage || MAJOR
Build sdist and wheel from sdist || Required frontend inputs, build script and assets all present || MAJOR
Missing/stale asset attack || Packaging fails explicitly instead of making viewer-less/old-setup wheel || MAJOR
Install into fresh environment outside checkout || Imports/assets come from site-packages; load setup and existing viewer || MAJOR
Runtime PATH without Node and CRISPResso || Both modes load and setup validates/previews without subprocess/backend attempts || BLOCKING
Offline browser/no arbitrary filesystem access || Local assets only; foreign Origin/Host and forged file handles rejected; no new unrestricted file server || BLOCKING'''
}
cases=[];chunks=[]
for group,text in groups.items():
    code=group.split()[0];section=[]
    for i,line in enumerate(text.splitlines(),1):
        title,expected,severity=line.split(' || ')
        row=dict(id=f'{code}{i:02}',group=group,title=title,expected=expected,severity_if_violated=severity,candidate_status='NOT RUN — no stable candidate',basis='User M11A scope plus pinned backend/design; see contract and oracle documents')
        cases.append(row);section.append(row)
    chunks.append('## '+group+'\n\n| ID | Attack / control | Required observation | Severity if violated |\n|---|---|---|---|\n'+'\n'.join('| '+r['id']+' | '+r['title']+' | '+r['expected']+' | '+r['severity_if_violated']+' |' for r in section)+'\n')
(ROOT/'case-inventory.json').write_text(json.dumps(cases,indent=2)+'\n')
(ROOT/'matrix-tables.md').write_text('\n'.join(chunks))
print(len(cases),'candidate audit cases prepared')
