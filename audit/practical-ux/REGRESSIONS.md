# Retained regression inventory (M)

Run from repository root with its pinned development venv. Test subsets are a compact first pass, not substitutes for the relevant full suite if tripwires fire. Keep host-lease/process suites serial, without simultaneous heavy jobs; the retained 30-second unrelated canary can expire normally under load. Do not rewrite M11C fixtures or expand known MINOR/INFO findings.

```bash
# Frozen oracle self-validation (baseline 0.8.0 only)
python -m pytest -q audit/practical-ux/test_oracles.py
python audit/practical-ux/audit_tools.py tripwire

# Setup and viewer boundaries
python -m pytest -q tests/test_m11_setup.py tests/test_m11_setup_edges.py tests/test_gui.py tests/test_gui_packaging.py

# Run, failure and final verification (small named retained subset)
python -m pytest -q \
 tests/test_m11b.py::test_accepted_spec_is_immutable_busy_and_early_cancel \
 tests/test_m11b.py::test_worker_failure_and_false_completion_are_not_published \
 tests/test_m11b.py::test_final_viewer_verification_failure_and_cancel_race \
 tests/test_m11b.py::test_job_endpoints_preserve_local_security

# Cancellation/containment, recovery auth and force: serial
python -m pytest -q \
 tests/test_m11c_process.py::test_detached_term_ignoring_descendant_is_reaped_before_cancelled \
 tests/test_m11c_recovery.py::test_recovery_preview_is_read_only_no_probe_or_executor \
 tests/test_m11c_recovery.py::test_force_preview_exact_backend_closure \
 tests/test_m11c_recovery.py::test_stale_recovery_confirmation_has_zero_destructive_effect \
 tests/test_m11c2_integrity.py::test_forged_ownership_and_matching_receipt_hash_still_fail_authentication \
 tests/test_m11c2_integrity.py::test_no_retroactive_or_circular_recovery_authentication

# PE/native counts and target vs copy gates
python -m pytest -q tests/test_m4.py

# Nuclease/qwc/TIGR + unchanged biological statistics/report pipeline
python -m pytest -q \
 tests/test_m8.py::test_qwc_normalization_and_identity \
 tests/test_m8.py::test_tigr_physical_coordinates \
 tests/test_m8.py::test_allele_partition_and_overlapping_memberships \
 tests/test_m8.py::test_backend_scientific_flags_are_verified \
 tests/test_m8.py::test_nuclease_m5_m6_statistics_determinism_and_no_recomputation \
 tests/test_m5.py::test_hand_enumerated_unpaired \
 tests/test_m5.py::test_hand_enumerated_paired \
 tests/test_m5.py::test_hand_calculated_bh \
 tests/test_m6.py

# Current UI regression suite and non-mutating build
(cd frontend && npm test && npx tsc --noEmit && npx vite build --outDir /tmp/audit-ui-build --emptyOutDir)
python viewer_build.py
```

Optional future end-to-end check once candidate input transport binding is ready:
`M4_INTEGRATION=1 python -m pytest -q tests/test_m4_integration.py` with the repository's pinned qualified Core runtime. Run the paired legacy/upload scientific fixture described in ORACLES.md; do not count mocked Core as this check. Other opt-in backend tests stay explicitly unrun unless relevant.

Version/package phase on the **future candidate**, after independent binding:

```bash
python audit/practical-ux/audit_tools.py version --root /path/to/candidate --expected 0.9.0
# From candidate working directory, with pinned dependencies:
python viewer_build.py
python -m build --no-isolation --outdir /tmp/audit-wheel
# Inspect that exact wheel with audit_tools.py version --wheel /tmp/audit-wheel/<exact-wheel>.whl
# Install that exact wheel in a new venv with pinned GUI deps, then:
python -c 'import importlib.metadata as m, peanalyzer; assert m.version("crispresso-pe-pipeline")==peanalyzer.__version__=="0.9.0"'
```

Also check actual server capabilities and visible UI version from the fresh wheel runtime. Candidate paths above are placeholders for a future separately authorized audit, not candidate branches inspected during prep. Run baseline-only self-tests on the frozen baseline environment; do not reinterpret their expected 0.8.0 or clean baseline tripwire as a candidate compatibility requirement.
