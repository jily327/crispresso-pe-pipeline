# Executed qualification matrix

<!-- final matrix -->
| Check | Final executed result |
|---|---|
| Full source | 2,000 passed, 102 skipped, 0 failed |
| Full installed wheel | 2,000 passed, 102 skipped, 0 failed |
| Focused source runtime/launcher | 30 passed |
| Genuine source Docker | All 8 distinct cases covered in aggregate; 2 strengthened boundary reruns passed |
| Genuine installed-wheel Docker | 8 passed in one final command |
| Frontend | 62 unit tests; type-check and clean build passed; assets identical |
| Linux Chromium | Run 6 passed; Recovery 7 + 1 corrected boundary rerun passed; no skips/automatic flaky retries |
| PE/nuclease parity | 39 + 35 comparisons passed on each installation |
| Packaging | Clean 1.0.1 wheel/sdist; repeat wheel bytes identical; 96 application files match |
| Windows / WSL / Excel | NOT VERIFIED IN THIS ENVIRONMENT |

Default skips comprise 94 existing backend-gated cases plus the 8 new opt-in Docker cases. The new eight were executed separately; the prior 94 were not rerun for this lifecycle-only follow-up. The earlier candidate's 94-case qualification is not counted as a new execution. The source full suite was supplemented by focused reruns after test-strengthening changes; production Python and frontend payloads stayed frozen. Browser tests were not duplicated against the wheel because its assets are byte-identical and installed-wheel lifecycle/backend behavior was directly exercised.

Environment: Linux, Python 3.12, genuine local Docker daemon, qualified CRISPResso2 2.3.4 image. Windows/WSL/Docker Desktop/Excel are not available. This follow-up qualifies the production wrapper, not the earlier qualification-only guard.

Final counts and artifact hashes are recorded in `test-results.json` and `packaging.json` after execution. Source and wheel tests import their respective installation; wheel import is asserted to reside in `site-packages`. Genuine tests opt in with `PEANALYZER_DOCKER_INTEGRATION=1`; default-suite backend skips are not hidden or relabeled as passes. Old 94-case backend qualification belongs to candidate 59e6755 and is not claimed as rerun here.

Commands:

```
python -m pytest -q
PEANALYZER_DOCKER_INTEGRATION=1 python -m pytest -q tests/test_docker_runtime_integration.py
npm test
npx tsc --noEmit
npm run build
playwright test --config playwright.run.config.ts
playwright test --config playwright.recovery.config.ts
python -m build --no-isolation
```

The full suite and browser/GUI suites run serially to respect the account's exclusive host lease. Browser tests use Linux Chromium and existing explicit test-only worker fixtures, with the shipped guarded runtime for real Core invocations. They do not substitute for the eight genuine daemon-containment cases or Windows hardware testing. The frontend source is unchanged; its existing 62 unit tests, type-check and clean production build are repeated.

## Unsuccessful intermediate attempts (retained, not counted as final passes)

- First genuine run: 4 passed, 1 failed. A 5,000-read GUI fixture spent the barrier budget in upstream routing; the test reduced synthetic volume to 200 reads per copy without changing production science or the nonempty-output requirement.
- A subsequent collection failed because the parity parametrization omitted its `mode` argument; corrected in the test signature.
- A genuine owner-death test reached stopped state but cleanup raced Docker auto-removal (HTTP 409). Production removed redundant manual DELETE, leaving daemon-owned auto-removal; test cleanup tolerates this transition after verifying identity. This was a real lifecycle correction, not a skipped assertion.
- Next run: 6 passed, 1 failed. A synthetic sentinel create exceeded the helper's 10-second daemon timeout; the fixture now allows 60 seconds. No scientific output comparison had failed.
- After switching production create to the Docker CLI, the test observer still read the old `Config.Cmd[0]` layout and missed a normally completed Core. Corrected observer to the control-directory argument; no containment failure was inferred from that test timeout.
- The final-source eight-case attempt passed all six containment/recovery cases, then its previous-candidate fixture invoked a version probe from an unmounted repository cwd. The fixture now runs from its mounted synthetic directory; both parity cases are rerun separately. This is reported as aggregate source coverage, not a green original eight-case command.
- The first browser Run suite hit its hardcoded 120-second PE completion wait while the GUI accurately remained RUNNING in metrics. The five following tests then received WORKER_BUSY because that job still owned the lease (six failed cases total). Browser timing is now configurable for genuine Docker execution; defaults remain unchanged. Qualification uses a 600-second test/job budget and 30-second ordinary assertion budget, with unchanged cancellation bounds and unchanged completion/safety assertions. Fresh fixtures are used for the rerun.
- Recovery browser qualification then passed seven cases and exposed a stale-snapshot assumption in its server-SIGKILL case: an escaped local child was gone, but the supervisor still held the lease during independent Docker confirmation when the preview was taken. The supervisor subsequently confirmed the container absent and released the lease; the old ACTIVE snapshot did not auto-refresh. The corrected test requests fresh read-only previews until the authoritative RESUMABLE state, then confirms and verifies completion. Only that changed boundary is rerun; browser results are reported as 6 Run + 7 Recovery + 1 corrected Recovery case, not one green eight-case Recovery command.
- An initial sandboxed default-suite invocation was stopped before completion and is not counted. The replacement full-suite runs use required loopback/process permissions.

Verbose logs and synthetic working directories remain outside Git. Compact results include independent daemon states, genuine guard exit codes, recovery/oracle results and archive hashes. No user laboratory data, URL tokens or private Windows paths are included.
