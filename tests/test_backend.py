import json
import subprocess
from pathlib import Path

import pytest

from peanalyzer.backend.pooled import BackendError, Executable, FIELDS, check_pooled_output, pooled_argv, preflight_guides, resolve_executable, run_pooled_diagnostic, validate_targets, write_amplicons
from peanalyzer.backend.synthetic import design
from peanalyzer.schemas import Target


@pytest.fixture
def targets():
    return [Target.model_validate(row) for row in design()["targets"]]


def test_tsv_exact_supported_columns_and_pe_override(tmp_path, targets):
    path = tmp_path / "targets with spaces.tsv"
    write_amplicons(path, list(reversed(targets)))
    lines = path.read_text().splitlines()
    assert lines[0].split("\t") == list(FIELDS)
    assert lines[1].split("\t")[0] == "SYN__copy1"
    assert lines[2].split("\t")[0] == "SYN__copy2"
    for line, target in zip(lines[1:], targets):
        row = dict(zip(FIELDS, line.split("\t")))
        assert row["prime_editing_override_prime_edited_ref_seq"] == target.prime_edited_sequence
        assert row["prime_editing_pegRNA_spacer_seq"] == target.pegRNA_spacer
        assert row["prime_editing_nicking_guide_seq"] == "NA"
    third = targets[1].model_copy(update={"copy_name": "copy3", "wt_sequence": targets[1].wt_sequence + "A", "prime_edited_sequence": targets[1].prime_edited_sequence + "A"})
    write_amplicons(tmp_path / "three.tsv", targets + [third])
    assert len((tmp_path / "three.tsv").read_text().splitlines()) == 4


def test_faithful_spacer_not_rewritten(tmp_path):
    targets = [Target.model_validate(row) for row in design(guide_mismatch=True)["targets"]]
    assert targets[0].pegRNA_spacer == targets[1].pegRNA_spacer
    assert targets[0].pegRNA_spacer in targets[0].wt_sequence
    assert targets[1].pegRNA_spacer not in targets[1].wt_sequence
    path = tmp_path / "mismatch.tsv"
    write_amplicons(path, targets)
    assert path.read_text().count(targets[0].pegRNA_spacer) >= 2


def test_mismatch_preflight_stops_before_execution(tmp_path, monkeypatch):
    targets = [Target.model_validate(row) for row in design(guide_mismatch=True)["targets"]]
    def unexpected(*args, **kwargs):
        pytest.fail("preflight must stop before any subprocess")
    monkeypatch.setattr("peanalyzer.backend.pooled.subprocess.run", unexpected)
    executable = Executable("missing", "2.3.4", {})
    with pytest.raises(BackendError, match="PE_GUIDE_REFERENCE_MISMATCH_UNSUPPORTED.*SYN__copy2"):
        run_pooled_diagnostic(r1=tmp_path / "missing1", r2=tmp_path / "missing2", targets=targets,
                              output=tmp_path / "unused", core=executable, pooled=executable)
    assert not (tmp_path / "unused").exists()


def test_preflight_accepts_spacer_reverse_complement(targets):
    from peanalyzer.schemas import reverse_complement
    preflight_guides(targets)
    preflight_guides([target.model_copy(update={"pegRNA_spacer": reverse_complement(target.pegRNA_spacer)}) for target in targets])


@pytest.mark.parametrize("case", ["empty", "duplicate", "extension", "case_collision"])
def test_target_preflight_failures(targets, case):
    if case == "empty": targets = []
    elif case == "duplicate": targets[1] = targets[0]
    elif case == "extension": targets[1] = targets[1].model_copy(update={"pegRNA_extension": "A" * 50})
    else: targets[1] = targets[1].model_copy(update={"copy_name": "COPY1"})
    with pytest.raises(BackendError): validate_targets(targets)


def test_deterministic_command_has_no_ambiguity_rescue():
    argv = pooled_argv("/some path/CRISPRessoPooled", child_core_command="/some path/CRISPResso")
    assert argv == pooled_argv("/some path/CRISPRessoPooled", child_core_command="/some path/CRISPResso")
    assert argv[0] == "/some path/CRISPRessoPooled"
    assert "--expand_ambiguous_alignments" not in argv and "--assign_ambiguous_alignments_to_first_reference" not in argv
    assert "--prime_editing_override_sequence_checks" not in argv
    assert argv[argv.index("--crispresso_command") + 1] == "'/some path/CRISPResso'"


@pytest.mark.parametrize("text,code", [("CRISPResso 2.3.4\n", 0), ("CRISPRessoPooled 2.3.4\n", 0), ("CRISPResso 2.3.3\n", 0), ("garbage", 0), ("CRISPResso 2.3.4", 1)])
def test_version_check(monkeypatch, text, code):
    monkeypatch.setattr("peanalyzer.backend.pooled.shutil.which", lambda _: "/fake/path")
    monkeypatch.setattr("peanalyzer.backend.pooled.subprocess.run", lambda *args, **kwargs: subprocess.CompletedProcess(args[0], code, text, ""))
    if text in ("CRISPResso 2.3.4\n", "CRISPRessoPooled 2.3.4\n"):
        assert resolve_executable("fake").version == "2.3.4"
    else:
        with pytest.raises(BackendError, match="VERSION_MISMATCH"): resolve_executable("fake")


def test_missing_executable(monkeypatch):
    monkeypatch.setattr("peanalyzer.backend.pooled.shutil.which", lambda _: None)
    with pytest.raises(BackendError, match="EXECUTABLE_MISSING"): resolve_executable("missing")


@pytest.mark.parametrize("failure", ["nonzero", "missing", "child", "success"])
def test_execution_failure_manifests_and_space_paths(tmp_path, targets, monkeypatch, failure):
    source = tmp_path / "input with spaces.gz"; source.write_bytes(b"synthetic placeholder for subprocess boundary test")
    output = tmp_path / "output with spaces"
    executable = Executable("/fake executable", "2.3.4", {"test": True})
    def run(argv, **kwargs):
        assert isinstance(argv, list) and not kwargs.get("shell", False)
        work = Path(kwargs["cwd"])
        assert " " not in str(work)
        assert (work / "input_R1.fastq.gz").read_bytes() == source.read_bytes()
        if failure in ("child", "success"):
            directory = work / "output/CRISPRessoPooled_on_diagnostic"; directory.mkdir(parents=True)
            (directory / "CRISPResso2Pooled_info.json").write_text(json.dumps({"running_info": {"version": "2.3.4", "end_time_string": "complete"}, "results": {"failed_batch_arr": ["SYN__copy1"] if failure == "child" else []}}))
        return subprocess.CompletedProcess(argv, 1 if failure == "nonzero" else 0)
    monkeypatch.setattr("peanalyzer.backend.pooled.subprocess.run", run)
    # Avoid monkeypatching subprocess.run used internally by provenance's Git probe.
    monkeypatch.setattr("peanalyzer.backend.pooled.software_provenance", lambda: {"pipeline_version": "test"})
    if failure == "success":
        run_pooled_diagnostic(r1=source, r2=source, targets=targets, output=output, core=executable, pooled=executable)
    else:
        with pytest.raises(BackendError):
            run_pooled_diagnostic(r1=source, r2=source, targets=targets, output=output, core=executable, pooled=executable)
    manifest = json.loads((output / "execution.json").read_text())
    assert manifest["status"] == ("completed" if failure == "success" else "failed")
    assert manifest["started_at"] and manifest["ended_at"]
    assert manifest["amplicons_sha256"] and manifest["target_configuration_sha256"] and manifest["inputs"]["r1"]["sha256"]
