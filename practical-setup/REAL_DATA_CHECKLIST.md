# Before real experimental data

**Do not use this candidate-specific setup package as audit approval.** Wait for
the final M11C.2 independent audit/merge, obtain the exact approved SHA/wheel,
and recheck these instructions if it differs from `232d380c73f456181bade0e5c11138c8c5ec6570`.

- [ ] Ubuntu/WSL2 x86_64, Python 3.12, installed wheel with matching GUI dependencies.
- [ ] Exact extracted native Core 2.3.4 runtime; doctor passes. A version string
  from an unrelated runtime is insufficient.
- [ ] Synthetic PE/nuclease practice appropriate to the intended mode completes
  and opens verified results. Confirm localhost from the actual Windows browser.
- [ ] Stable Linux-side input/output paths; enough disk for raw reads, preparation,
  backend results and preserved provenance. No active `/mnt/c`/network workspace.
- [ ] Correct synchronized R1/R2 of one raw pool, or complete verified external
  M2 archive. Record source checksums before registration; retain original data.
- [ ] Expected barcode pairs and library layout confirmed experimentally.
  Trims are intentional; no guess based solely on the Hi-TOM name.
- [ ] Every sample has correct barcode ID, editor/treatment/dpi and biological
  replicate/block metadata. Controls use a documented lab convention, not an
  invented value from a tutorial.
- [ ] PE: one biological target, correct WT/intended sequences for all copies,
  real shared guides/extensions. Nuclease: one copy, correct explicit window or
  TIGR profile/18-nt target/window choice.
- [ ] All Review errors resolved; all warnings understood. Scientific blocks are
  retained, not bypassed. Output parent exists, proposed child does not.
- [ ] Recovery limitations understood: `/tmp` key loss may prevent incomplete
  recovery. Computer/server stay running; do not assume power loss is recoverable.
- [ ] Original sources, the full workspace and hidden `.NAME.gui-inputs-JOB_ID`
  siblings will remain at their recorded paths. No cleanup/relocation plan that
  deletes provenance.
- [ ] After Run, use **Open Results** only after authoritative completion. Review
  counts/status/denominator definitions before interpreting biology.

Keep tokens, recovery keys and private experimental data out of GitHub issues.
For support, share package/candidate/runtime versions and the visible error code,
with sensitive paths and labels redacted.
