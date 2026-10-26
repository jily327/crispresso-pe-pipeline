import pytest
from pydantic import ValidationError

from peanalyzer.schemas import Config, Sample, Target
from peanalyzer.validation import MetadataError, load_config, validate_metadata


@pytest.mark.parametrize("text", [
    "", "[]", "schema_version: 2", "schema_version: true", "schema_version: 1.0",
    "schema_version: '1'", "schema_version: 1\nn_processes: 0",
    "schema_version: 1\nn_processes: true", "schema_version: 1\nn_processes: '2'",
    "schema_version: 1\ncpu: 2", "schema_version: 1\ndemux:\n  max_mismatches: -1",
    "schema_version: 1\ndemux:\n  ambiguous_policy: first",
    "schema_version: 1\ndemux:\n  trim_barcodes: 1",
    "schema_version: 1\ndemux:\n  trim_bridges: true",
    "schema_version: 1\nqc:\n  max_ambiguous_fraction: 1.1",
    "schema_version: 1\nqc:\n  min_copy_fraction: .nan",
    "schema_version: 1\ncrispresso:\n  version: '2.2.0'",
    "schema_version: 1\ncrispresso:\n  expand_ambiguous_alignments: true",
    "schema_version: 1\nquantification:\n  primary_metric: modified",
    "schema_version: 1\nschema_version: 1",
    "schema_version: 1\ndemux:\n  max_mismatches: 0\n  max_mismatches: 1",
    "schema_version: 1\nstatistics:\n  mode: factorial",
    "schema_version: 1\nstatistics:\n  factors: [editor]",
    "schema_version: 1\nstatistics:\n  mode: simple\n  factors: [editor, editor]",
    "schema_version: 1\nstatistics:\n  mode: simple\n  factors: [editor]\n  include_interaction: true",
    "!!python/object/apply:os.system ['echo should-not-run']",
    "schema_version: 1\n1: wrong",
])
def test_invalid_config_rejected(tmp_path, text):
    path = tmp_path / "config.yaml"
    path.write_text(text)
    with pytest.raises(MetadataError):
        load_config(path)


def test_defaults_and_machine_readable_schemas():
    config = Config(schema_version=1)
    assert config.demux.max_mismatches == 0
    assert config.demux.trim_barcodes is False
    assert config.demux.trim_bridges is False
    assert config.statistics.mode == "none"
    for model in (Config, Sample, Target):
        schema = model.model_json_schema()
        assert schema["additionalProperties"] is False
        assert schema["type"] == "object"
    with pytest.raises(ValidationError):
        Config(schema_version=1, n_processes=1.5)


def test_paired_statistics_requires_block_id(example_dir, tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("schema_version: 1\nstatistics:\n  mode: factorial\n  factors: [editor, treatment]\n")
    with pytest.raises(MetadataError, match="block_id"):
        validate_metadata(example_dir / "samples.csv", example_dir / "targets.csv", config)


def test_factorial_metadata_is_not_power_validation(example_dir, tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("schema_version: 1\nstatistics:\n  mode: factorial\n  factors: [editor, treatment]\n  block_column: block_id\n  include_interaction: true\n")
    report = validate_metadata(example_dir / "samples.csv", example_dir / "targets.csv", config)
    assert any("power" in warning for warning in report["warnings"])


def test_requested_block_column_requires_complete_values(tmp_path, target_data, sample_data, write_csv):
    sample_data.update(paired="false", block_id="")
    samples = write_csv("samples.csv", [sample_data])
    targets = write_csv("targets.csv", [target_data])
    config = tmp_path / "config.yaml"
    config.write_text("schema_version: 1\nstatistics:\n  mode: simple\n  factors: [editor]\n  block_column: block_id\n")
    with pytest.raises(MetadataError, match="nonempty block_id"):
        validate_metadata(samples, targets, config)
