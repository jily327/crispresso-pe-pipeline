# Release readiness — Docker containment follow-up

**PASS WITH CONDITIONS.** The supported guarded Docker workflow passes Linux qualification. PR #16 is suitable for maintenance review/merge with the compatibility limits below accepted. This is not approval for routine Windows deployment before the final actual-PC smoke test. No merge or release tag was performed.

The legacy persistent-container model was independently reproduced leaving genuine Core alive after local client SIGKILL. The shipped replacement uses one pinned-image container per invocation, a wrapper-owned kernel lease, a separate production-supervisor lease for GUI work, and independent daemon observation before GUI containment confirmation. Genuine installed-wheel tests pass all eight cases, including nonempty partial backend failure, wrapper/CLI/supervisor death, completion race, repeated cancellation/recovery, foreign-file preservation, unrelated-container isolation and PE/nuclease parity.

Final qualification:

- Source: 2,000 passed / 102 backend-gated skips; installed wheel: 2,000 passed / 102 backend-gated skips. The existing 94 gated backend cases were not rerun in this follow-up; their earlier candidate qualification remains separately recorded.
- Genuine pinned Docker: all eight distinct cases covered from source (aggregate runs); one final installed-wheel command passed 8/8. Two strengthened source boundary cases and 30 focused source tests also passed.
- Frontend: 62 unit tests, type-check and production build passed; rebuilt assets are identical. Linux Chromium Run and Recovery suites: 14 distinct cases passed (Run 6; Recovery 7 plus one corrected boundary rerun), no skips or automatic flaky retries. Initial browser timing failures remain documented.
- Scientific parity: PE 39/39 and nuclease 35/35 comparisons on each installation; known-truth counts, statistics, HTTP and PE workbook values agree with previous candidate 59e6755. Historical output bytes and mtimes remain unchanged.
- Clean 1.0.1 wheel and sdist validated; all 96 packaged application files match the tested source and installed wheel. Repeat wheel bytes are identical. New Python regressions and relevant browser tests/configurations are included in the source archive.

Scientific algorithms, metrics, denominators, classification, reconstruction, routing and statistics are unchanged. The only existing Python module changed by this follow-up is GUI supervision; the two new modules manage Docker lifecycle. Recovery authentication/publication/deletion modules are unchanged from candidate 59e6755. The original v1.0.0 scientific freeze evidence is retained separately.

Remaining deployment gates and limits:

1. **Windows 11 / WSL Ubuntu-24.04 / Docker Desktop / Microsoft Excel / Explorer and final-byte launcher behavior: NOT VERIFIED IN THIS ENVIRONMENT.** Run the exact synthetic installation and manual checklist in `docs/docker-runtime-1.0.1.md` on the actual PC. Earlier user-reported success is not evidence for these new bytes. The shared lock/UID behavior must pass the real guard probe; never bypass it.
2. Install beside the old release, qualify first, then switch `peanalyzer-current`. The user's original wrapper and installation were not remotely modified. Keep the permanent BAT, original analysis folders and account credentials. Rollback changes only the symlink and restores the old wrapper's known cancellation limitation.
3. F-01 remains partial for legacy unauthenticated nonempty interrupted output. Preserve it and rerun in a fresh workspace. Missing original recovery credentials cannot be recreated. No foreign-content deletion or authentication bypass is introduced.
4. Arbitrary external wrappers are not automatically qualified. The supported desktop launcher enforces the shipped entry point. Local daemon access, matching file ownership and shared kernel locks are prerequisites; remote Docker is unsupported. Daemon unavailability leaves containment unconfirmed and retains the host lease.
5. Private diagnostics/failed attempts are retained; an interrupted create may leave inert Created container metadata. No blanket cleanup is authorized. Per-invocation creation and version probes add startup overhead compared with the old persistent container.
6. The local daemon confirms the qualified image for the new runtime. Historical scientific JSON still carries its declared/unverified provenance meaning; there is no retroactive or cryptographic hardware attestation claim.

See TEST_MATRIX.md and test-results.json for exact runs, skipped suites and unsuccessful intermediate attempts. See RECOVERY_ADVERSARIAL_RESULTS.md and wheel-evidence/ for actual daemon states and recovery results. A favorable verdict does not waive the Windows gate or authorize a merge.
