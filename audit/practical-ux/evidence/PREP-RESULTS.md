# Preparation validation (2026-10-29 UTC)

Baseline main: 72e0f86a495e079cab2ae50d2796e7a3423c78af.

| Check | Observed result |
|---|---|
| Frozen baseline oracle suite | 13 passed, 1.63 seconds; `oracles.txt` |
| Selected existing retained tests | 9 passed, one existing Starlette/AnyIO deprecation warning, 7.09 seconds; `retained.txt` |
| Frozen-core comparison against untouched main | zero differences; `tripwire.json` |
| Future candidate adapter tests | 66 collected; NOT EXECUTED; `future-collection.txt` |
| XLSX structural cross-check | All 29 readable by installed openpyxl; formula, date, hidden rows/columns, merged cells and 20 samples explicitly inspected |
| Fixture regeneration | All generated XLSX/FASTQ and case-index hashes identical after independent output-directory regeneration |
| Audit Python modules | Parsed successfully |

Retained command actually executed (not the entire inventory):

```
python -m pytest -q \
 tests/test_m11_setup.py::test_valid_pe_no_execution_or_file_writes \
 tests/test_gui.py::test_local_access_and_capabilities \
 tests/test_m11b.py::test_final_viewer_verification_failure_and_cancel_race \
 tests/test_m8.py::test_qwc_normalization_and_identity \
 tests/test_m5.py::test_hand_calculated_bh
```

No large qualification, real Core execution, candidate endpoint, candidate browser test or version-0.9.0 runtime was run during prep. The original full regression list is a future audit inventory, not a claim of executed coverage. Main has no browser upload/XLSX feature to test; adapter tests intentionally require later independent binding. Earlier cloud-onboarding test results are not substituted for this prep's evidence.

One deprecation warning is recorded as INFO compatibility context, not a new application defect. No newly confirmed pre-existing scientific or M11C defect was found; existing known M11C MINOR/INFO issues remain out of scope.

All outputs are synthetic audit fixtures. The gzip files are force-added by exact path because the repository correctly ignores sequencing data globally. No ignore rule or production file was changed.
