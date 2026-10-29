# Future candidate binding, not implementation knowledge

`audit_candidate.py` is deliberately not default pytest discovery. Explicit command:

```
python -m pytest -q -p auditor_candidate_binding audit/practical-ux/audit_candidate.py
```

The future independent auditor supplies a separate plugin exposing a **function-scoped** `audit_adapter` fixture. No adapter exists in this frozen prep; invoking it without a binding errors rather than passing/skipping. Bind real routes/DTOs and test-owned barriers; do not implement missing candidate behavior in the adapter. Report unsupported fault-injection boundaries as NOT TESTED, not a pass. Read-only inspection helpers must not return fabricated expected values. Record plugin SHA and diff separately from frozen oracle SHA. Never edit baseline fixtures to accommodate an observed result.

Interface:

- `upload(name, chunks)`, `upload_file_in_chunks(path, chunk_size)` send multipart bytes over HTTP. Return accepted flag and opaque capability. `registered_bytes`, `registered_identity` inspect actual server registered file through private test instrumentation; identity is integer byte size and SHA-256.
- `is_owned_regular_file` and `path_controlled_by_client` inspect no-follow file/parent ownership and containment, not filename cosmetics. `victim_snapshot` covers ALL explicitly seeded external files, inode/mode/mtime/size/hash; it includes the external legacy input even when not selected.
- `accepted_capabilities` and `accepted_partial_files` query actual Setup registration and validate current drafts; response 200 alone is not acceptance evidence. `staging_safe_after_settle` accounts for all test-owned leftovers after documented cleanup deadline and shutdown.
- `interrupt_upload` aborts actual body transmission or injects an exception at an existing server boundary. `upload_with_owned_staging_fault` synchronizes filesystem substitution only inside disposable server-owned test directories. Add the external victim before capturing snapshot. No changes to production or M11C fixtures.
- `send_path_instead_of_file` exercises JSON, form-data filename/body, and text representations; owned-workspace/other-analysis/legacy-input resolve to the test's external victim paths, never private real data.
- `register_external_fixture`, `replace_selected_upload`, `cleanup_uploads`, `external_exists` exercise documented legacy registration and upload cleanup. Restart/shutdown cleanup and concurrent-draft retention are additional U13 cases in ORACLES.md.
- `import_workbook` uses actual uploaded XLSX bytes. `draft_snapshot` includes revision, rows, validation status, preview and capability registrations. `canonical_imported_samples` returns backend normalized Sample model dumps. `authoritative_manual_equivalent` uses frozen fixture row values and current qualified loaders/compiler; it must never derive its expected rows from the parser under test. Adapt coordinates only if the downloaded official template differs, with documented contract binding.
- `import_with_catalog_probe` patches the actual existing backend catalog object/provider before import and records calls. Probe fresh instance on every call; never replace parser output or duplicate its mapping.
- `generate_large_fastq` calls the frozen generator with increasing pairs until actual compressed bytes exceed the requested size. `streaming_evidence` records bounded-read instrumentation and two-size memory experiment, with timestamps and framework spool configuration. If memory instrumentation unavailable, return an explicit test limitation; do not set the boolean to true by default.

Extend this binding with the browser cases and scientific execution parity from ORACLES.md. The generic tests alone are not a complete audit. Labels/HTTP route names are not pre-imposed where the feature contract did not define them.

Additional methods for the frozen UI/parity cases:

- `render_metric_scenario` intercepts only presentation transport, then renders real candidate components. `visible_metric_cells(key)` extracts actual rendered text for sample/target/metric/copy/policy; converts documented absence marker to None but performs no numeric conversion, fraction formatting or calculation. The simultaneous-primary-columns assertion must query Samples view, not only Overview cards. Mixed-copy case must preserve target metrics. `primary_metrics_precede_copy_diagnostics` inspects DOM order AND visible group labels, not array order alone.
- `deliver_job_frame` maps the synthetic timeline to current API DTO/event transport; `authoritative_job_state` reads unmodified response state. Tests here establish presentation only. Actual finalization/cancel/failure barriers remain required by B07/B12. `deliver_terminal_after_verification` resets each scenario to a verification-phase job before delivering the specified state, rather than transitioning an already-completed job.
- `actual_current_versions` reads each named authority independently (fresh wheel installation/server/visible header included). It must not return one version string repeated. `historical_evidence_unchanged` runs hash checks; `static_build_identity_valid` runs the repository identity gate and inspects its exit status.
- `execute_identical_bytes_both_paths` runs both synthetic scientific workflows with the same pinned real Core. Return raw sources plus the named explicit semantic projections listed in the test. Expected projections are auditor code, not candidate normalization. `identity_differences_follow_frozen_constituents` must emit an evidence report of every changed constituent; no wildcard stripping, no comparison of opaque digests as if content-only. Transport/display scenarios do not replace these real executions.
