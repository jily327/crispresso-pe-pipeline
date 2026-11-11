# Windows smoke-test record

**Current status: NOT VERIFIED IN THIS ENVIRONMENT.** This environment is Linux; it does not provide Windows, WSL or Microsoft Excel.

The user reports successful testing on a real Windows PC with WSL Ubuntu-24.04 and Docker Desktop: BAT launch, automatic browser opening, theme persistence, historical workspace discovery/opening, completed analysis, Explorer behavior, Excel creation/interaction, continued Results verification, and manual output-folder opening. This is user-reported manual success, not an independently observed automated result. It does not establish that the exact final launcher bytes were tested.

Record tester/date, Windows build, WSL version/distro, Docker Desktop version, Excel version, release commit and SHA-256 of both launcher files. Do not record private paths or the fragment token in screenshots/logs.

1. Install v1.0.1 in a new release directory. Repoint `~/peanalyzer-current` to it; keep the permanent BAT unchanged. Keep `PEANALYZER_LIBRARY_ROOT` stable and retain all prior registered library roots. Never move old analysis folders.
2. Cold-start the BAT with Docker Desktop stopped. Confirm bounded Docker startup, the correct WSL distro, one local server and default Windows browser opening. Test an unavailable Docker/distro and missing release environment; errors must be actionable.
3. Use paths containing spaces. Toggle Light/Dark and relaunch. Confirm prior v0.8/v0.9/v1.0 workspaces remain discoverable and require verification before Results. Check completed historical results without modifying their files.
4. Import a synthetic sheet and hand-type a whitespace-padded barcode. Review identities, run, and compare stored primary count pairs with Results and Excel. Open/edit/close Excel while Results remains verified. Confirm Explorer/manual folder opening.
5. Cancel during a backend run after files exist. Independently confirm the deployed wrapper's owned Docker container/backend has stopped before recovery; a CANCELLED GUI label alone does not prove daemon-process containment. Plain Docker CLI signal proxying failed this check in Linux qualification. Confirm no COMPLETED marker; inspect recovery and resume. The attempt diagnostics should remain outside the workspace; the resumed result must verify. Repeat with metrics force.
6. Close the launcher normally and during startup. Confirm server shutdown and private token-log removal. Browser auto-open failure must leave a printed local URL fallback.
7. With a synthetic interrupted workspace, record the recovery key's SHA-256 (never its bytes), run `wsl --shutdown`, restart and confirm the persistent key survives. Verify no active backend before following the existing stale-lock procedure. Recover the workspace. Repeat after Windows restart.
8. Simulate missing credentials only on a disposable test account/key backup. Confirm fail-closed UNSUPPORTED with a key explanation, no deletion, and successful authentication after restoring the original key.

Outcome: NOT EXECUTED here. Record each step PASS/FAIL and attach redacted evidence before Windows desktop approval.
