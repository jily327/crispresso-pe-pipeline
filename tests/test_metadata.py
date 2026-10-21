import pytest

from peanalyzer.schemas import Config, reverse_complement
from peanalyzer.validation import (
    MetadataError, load_samples, load_targets, metadata_warnings, validate_metadata,
)


def test_examples_validate_and_report_scope(example_dir):
    report = validate_metadata(example_dir / "samples.csv", example_dir / "targets.csv", example_dir / "config.yaml")
    assert report["status"] == "valid_metadata"
    assert (report["sample_count"], report["target_count"], report["copy_count"]) == (2, 1, 2)
    assert report["resolved_config"]["quantification"]["primary_metric"] == "precise_full_amplicon"
    assert any("routing" in warning for warning in report["warnings"])
    assert "metadata only" in report["scope"]


def test_variable_barcode_lengths_and_literal_replicate_id(sample_data, write_csv):
    second = dict(sample_data, sample_name="sample2", barcode_id="B", forward_barcode="TTTTTT", reverse_barcode="GGG")
    rows = load_samples(write_csv("samples.csv", [sample_data, second]))
    assert len(rows[1].forward_barcode) == 6
    assert len(rows[1].reverse_barcode) == 3
    assert rows[0].biological_replicate == "01"


@pytest.mark.parametrize("column,value", [
    ("sample_name", "../escape"), ("barcode_id", "a b"), ("forward_barcode", "AANN"),
    ("reverse_barcode", "AUCG"), ("forward_barcode", ""), ("forward_barcode", "AA AA"),
    ("dpi", "-1"), ("dpi", "6.5"), ("dpi", "true"), ("paired", "yes"),
    ("paired", "1"), ("block_id", ""), ("editor", ""), ("treatment", ""),
])
def test_invalid_sample_fields_have_row_context(sample_data, write_csv, column, value):
    sample_data[column] = value
    with pytest.raises(MetadataError, match="row 2"):
        load_samples(write_csv("samples.csv", [sample_data]))


def test_unpaired_can_have_no_block(sample_data, write_csv):
    sample_data.update(paired="false", block_id="", forward_barcode=" aaaa ")
    row = load_samples(write_csv("samples.csv", [sample_data]))[0]
    assert row.block_id is None
    assert row.forward_barcode == "AAAA"


@pytest.mark.parametrize("duplicate", ["sample_name", "barcode_id", "pair"])
def test_duplicate_sample_keys_rejected(sample_data, write_csv, duplicate):
    second = dict(sample_data, sample_name="sample2", barcode_id="B", reverse_barcode="GGGG")
    if duplicate == "pair":
        second["reverse_barcode"] = sample_data["reverse_barcode"]
    else:
        second[duplicate] = sample_data[duplicate]
    with pytest.raises(MetadataError, match="duplicate"):
        load_samples(write_csv("samples.csv", [sample_data, second]))


@pytest.mark.parametrize("kind", ["duplicate_header", "unknown_header", "missing_header", "extra_cell", "missing_cell", "empty", "header_only", "malformed_quote"])
def test_malformed_csv_rejected(tmp_path, sample_data, kind):
    header, row = list(sample_data), list(sample_data.values())
    if kind == "duplicate_header":
        header[-1] = header[-2]
    elif kind == "unknown_header":
        header[-1] = "paried"
    elif kind == "missing_header":
        header.pop()
        row.pop()
    elif kind == "extra_cell":
        row.append("extra")
    elif kind == "missing_cell":
        row.pop()
    text = ",".join(header) + "\n" + ",".join(row) + "\n"
    if kind == "empty":
        text = ""
    elif kind == "header_only":
        text = ",".join(header) + "\n"
    elif kind == "malformed_quote":
        text = ",".join(header) + '\n"unclosed'
    path = tmp_path / "bad.csv"
    path.write_text(text)
    with pytest.raises(MetadataError):
        load_samples(path)


def test_rna_normalization_and_optional_columns(target_data, write_csv):
    target_data.update(pegRNA_extension="ucgaaa", nicking_guide="uugg", pegRNA_scaffold="ggcu")
    target_data["quantification_window_coordinates"] = "0-2_5-7"
    target_data["quantification_window_center"] = "-3"
    target_data["prime_editing_pegRNA_scaffold_min_match_length"] = "2"
    row = load_targets(write_csv("targets.csv", [target_data]))[0]
    assert row.pegRNA_extension == "TCGAAA"
    assert row.nicking_guide == "TTGG"
    assert row.amplicon_id == "synthetic__copy1"
    assert row.quantification_window_center == -3


@pytest.mark.parametrize("column,value", [
    ("wt_sequence", "AAAN"), ("prime_edited_sequence", "..."), ("pegRNA_spacer", ""),
    ("pegRNA_extension", "AG-X"), ("copy_name", "copy__1"), ("target_name", "../target"),
    ("quantification_window_coordinates", "3-1"), ("quantification_window_coordinates", "0-16"),
    ("quantification_window_coordinates", "1-3_3-4"), ("quantification_window_coordinates", "2-3,4-5"),
    ("quantification_window_size", "-1"), ("quantification_window_center", "1.2"),
    ("prime_editing_pegRNA_scaffold_min_match_length", "2"),
])
def test_invalid_target_fields(target_data, write_csv, column, value):
    target_data[column] = value
    with pytest.raises(MetadataError, match="row 2"):
        load_targets(write_csv("targets.csv", [target_data]))


def test_intended_indel_references_are_allowed(target_data, write_csv):
    target_data["prime_edited_sequence"] += "AC"
    row = load_targets(write_csv("targets.csv", [target_data]))[0]
    assert len(row.prime_edited_sequence) != len(row.wt_sequence)


def test_identical_wt_and_pe_rejected(target_data, write_csv):
    target_data["prime_edited_sequence"] = target_data["wt_sequence"]
    with pytest.raises(MetadataError, match="must differ"):
        load_targets(write_csv("targets.csv", [target_data]))


@pytest.mark.parametrize("kind", ["id", "sequence", "reverse_complement"])
def test_duplicate_targets_rejected(target_data, write_csv, kind):
    second = dict(target_data, copy_name="copy2")
    if kind == "id":
        second.update(copy_name="copy1", wt_sequence=target_data["wt_sequence"] + "A")
    elif kind == "reverse_complement":
        second["wt_sequence"] = reverse_complement(target_data["wt_sequence"])
    with pytest.raises(MetadataError, match="duplicate"):
        load_targets(write_csv("targets.csv", [target_data, second]))


def test_backend_palindrome_limitation(target_data, write_csv):
    target_data["wt_sequence"] = "ACGT"
    with pytest.raises(MetadataError, match="palindromic"):
        load_targets(write_csv("targets.csv", [target_data]))


@pytest.mark.parametrize("mismatches,second_forward,second_reverse", [
    (0, "AAAAAA", "CCCCCC"), (1, "AATT", "CCGG"),
])
def test_potential_barcode_ties_warn(sample_data, target_data, write_csv, mismatches, second_forward, second_reverse):
    second = dict(sample_data, sample_name="sample2", barcode_id="B", forward_barcode=second_forward, reverse_barcode=second_reverse)
    samples = load_samples(write_csv("samples.csv", [sample_data, second]))
    targets = load_targets(write_csv("targets.csv", [target_data]))
    warnings = metadata_warnings(samples, targets, Config(schema_version=1, demux={"max_mismatches": mismatches}))
    assert any("barcode matching may be ambiguous" in warning for warning in warnings)


def test_pe_reference_collisions_warn(target_data, sample_data, write_csv):
    second = dict(target_data, copy_name="copy2", wt_sequence="AAACCCGGGTTTACGC")
    targets = load_targets(write_csv("targets.csv", [target_data, second]))
    samples = load_samples(write_csv("samples.csv", [sample_data]))
    assert any("reference collision" in w for w in metadata_warnings(samples, targets, Config(schema_version=1)))


def test_missing_file_is_metadata_error(tmp_path):
    with pytest.raises(MetadataError, match="missing.csv"):
        load_samples(tmp_path / "missing.csv")


def test_reverse_complement_barcode_orientation_affects_prefix_warnings(sample_data, target_data, write_csv):
    sample_data["reverse_barcode"] = "CCAA"
    second = dict(sample_data, sample_name="sample2", barcode_id="B", reverse_barcode="TTCCAA")
    samples = load_samples(write_csv("samples.csv", [sample_data, second]))
    targets = load_targets(write_csv("targets.csv", [target_data]))
    default = metadata_warnings(samples, targets, Config(schema_version=1))
    reverse = metadata_warnings(samples, targets, Config(schema_version=1, demux={"reverse_barcode_orientation": "reverse_complement"}))
    assert not any("barcode matching" in warning for warning in default)
    assert any("barcode matching" in warning for warning in reverse)


def test_scaffold_match_length_cannot_exceed_sequence(target_data, write_csv):
    target_data.update(pegRNA_scaffold="AC", prime_editing_pegRNA_scaffold_min_match_length="3")
    with pytest.raises(MetadataError, match="exceeds scaffold length"):
        load_targets(write_csv("targets.csv", [target_data]))


def test_bad_reference_orientation_is_a_visible_warning(sample_data, target_data, write_csv):
    target_data.update(pegRNA_spacer="TTTTTT", pegRNA_extension="CCCCCC")
    samples = load_samples(write_csv("samples.csv", [sample_data]))
    targets = load_targets(write_csv("targets.csv", [target_data]))
    warnings = metadata_warnings(samples, targets, Config(schema_version=1))
    assert any("spacer is not an exact forward" in warning for warning in warnings)
    assert any("extension is absent" in warning for warning in warnings)
