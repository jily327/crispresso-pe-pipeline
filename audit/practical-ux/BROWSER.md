# Browser audit plan (N)

Use Chromium and, when available, Firefox; use one worker for Run/Recovery host lease tests. Capture screenshots, Playwright trace, exact candidate/server versions, request bodies (without launch token), event sequence, and downloaded file hashes. A Linux browser automation run does not establish native Windows OS coverage; report native-Windows check separately.

The future auditor binds accessible selectors and real routes from the official candidate UI; the behaviors below stay frozen. Use the actual local session token and loopback server, not public preview/proxy. DOM fixtures can test rendering but cannot establish real upload or scientific completion. Use current main `frontend/src/tests/fixtures/{pe,nuclease}.json` for read-only projection regressions and `fixtures/metric-display.json` for deliberate edge cases.

Actual browser upload primitive (fixture is read by the browser automation client, not sent as a server path):

```ts
await page.getByLabel(r1AccessibleLabel).setInputFiles({
  name: 'R1.fastq.gz', mimeType: 'application/gzip',
  buffer: await fs.readFile(fixturePath),
});
```

For a Windows-origin filename use a buffer payload name containing backslashes/drive text; inspect multipart filename and server registration. Browser-native file chooser may normalize basename; assert that normalized or malicious supplied name cannot choose a server destination. Do not assign `C:\\fakepath` into input.value or submit it as the body. Also run `setInputFiles(actualFixturePath)` and two sequential selections of the same file.

| Case | Actions and frozen assertions |
|---|---|
| B01 Windows input | Normal Windows chooser basename, backslash/drive attack, Unicode name and duplicate names. Capability remains opaque, file bytes exact, no server path disclosure or victim mutation. |
| B02 upload/replace | Select R1/R2, replace after validation, same name/different bytes, same bytes/new name, cancel mid-body with page/context close; reload. Only complete registered bytes selectable; replacement invalidates Review; other draft/job inputs survive. |
| B03 template download | Real download event; save XLSX, verify ZIP/worksheet/header structure, no formulas/macros/external links, record hash; original template import follows advertised contract. |
| B04 Excel import | Use all workbook fixtures through file-input API. Compare editable rows and visible row/column errors to fixture oracle. Atomic failure; do not silently skip hidden/blank/formula data. |
| B05 editable rows | Change imported replicate/treatment, add/remove row, switch library profile. Draft revision increments; preview invalidated; revalidate canonical fields match manual path. |
| B06 Validate & Review | Both manual and Excel equivalent rows with same registrations; preview science/config/DAG equal. No stage execution or output workspace creation during import/review. |
| B07 verification | Hold real worker at FINAL_VALIDATION, then viewer registration barrier. Show prominent final-verification text and 100% *stage completion*, state RUNNING; no premature Open Results. Release to actual verified COMPLETED. Test reload, paginated events, failure, cancellation and late responses. |
| B08 Samples metrics | Both primary PE columns simultaneously for every sample, regardless of selected diagnostic series. Assert stored count strings, denominators, percent strings, status and missing comparator. Include >2^53 and null. No derived values from JS division. |
| B09 definitions | Keyboard focus + Enter/Space opens info; Escape closes and restores focus, associated accessible name, readable tooltip on hover/focus; definitions match H. No interpretation claims. |
| B10 grouping | Primary target metrics first; copy-specific chr01/chr11 visibly separate diagnostics with routing-conditioning language. Blocked chr11 leaves target metrics intact. |
| B11 nuclease | No PE-only metric columns required; exclusive classes remain exclusive, overlapping classes labelled not additive, qwc/TIGR display and stored counts unchanged; source download still exact. |
| B12 Run/Recovery | Existing new-run, cancel-confirm, final-verification failure, Inspect Recovery, resume preview, advanced force confirmation, stale revision and forged identity denial; inherited host lease and terminal events unchanged. Existing E2E suites in frontend/e2e, e2e-run, e2e-recovery are retained entry points. |

Transport test fault barriers must be separate from M11C fixtures. Drive real filesystem checks via test-owned helpers; do not expose server filesystem inspection endpoints. Browser UI assertions must not trust a hidden DOM JSON blob instead of visible text/table association. A mock timeline passes a presentation test only; real worker/registration barrier checks remain required before future approval.
