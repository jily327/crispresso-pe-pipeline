import pytest

from peanalyzer.barcodes import (
    Barcode, BarcodeMatch, Catalog, assign_barcode_pair, bundled_catalog, extract_barcode,
    extraction_rules, identify_barcode, load_catalog,
)
from peanalyzer.schemas import Config, DemuxConfig
from peanalyzer.validation import MetadataError, load_samples


def test_bundled_catalog_and_profile():
    catalog = load_catalog(bundled_catalog())
    assert len(catalog.ends["forward"]) == 12
    assert len(catalog.ends["reverse"]) == 8
    assert catalog.ends["forward"]["F2"] == "GCTTGTAGT"
    assert catalog.ends["reverse"]["RC"] == "CTGTACGCT"
    rules = extraction_rules(DemuxConfig(), catalog)
    for rule in rules.values():
        assert (rule.start, rule.length) == (0, 9)
    assert rules["forward"].bridge == "GGAGTGAGTACGGTGTGC"
    assert rules["reverse"].bridge == "GAGTTGGATGCTGGATGG"
    assert extract_barcode(b"GCTTGTAGTGGAGTGAGTACGGTGTGC", rules["forward"], 9) == "GCTTGTAGT"


def test_real_sample_mapping(example_dir):
    catalog = load_catalog(bundled_catalog())
    samples = load_samples(example_dir / "ev_only_1005_samples.csv", catalog, metadata_required=False)
    assert len(samples) == 12
    assert samples[0].model_dump() == {
        "sample_name": "ePPEmax-v2-EV_leaf1", "barcode_id": "1B", "forward_barcode_id": "F1",
        "reverse_barcode_id": "RB", "forward_barcode": "GCTTGCGTT", "reverse_barcode": "CTGTGTAGT",
    }


@pytest.mark.parametrize("direction,key,observation,status,expected", [
    ("forward", 9, "GCTTGCGTT", "recognized", "F1"),
    ("forward", 9, "ACTTGCGTT", "recognized", "F1"),
    ("forward", 9, "GCTTGCTTT", "ambiguous", None),
    ("forward", 9, "NCTTGCGTT", "unknown", None),
    ("forward", 9, "GCTT", "unknown", None),
    ("reverse", 9, "CTGTACGCT", "recognized", "RC"),
])
def test_independent_hamming_matches(direction, key, observation, status, expected):
    catalog = load_catalog(bundled_catalog())
    match = identify_barcode({key: observation}, catalog.ends[direction], 1)
    assert (match.status, match.barcode_id) == (status, expected)
    if status == "ambiguous":
        assert set(match.candidates) == {"F1", "F5"}


def test_exact_default_does_not_rescue_or_search():
    catalog = load_catalog(bundled_catalog())
    match = identify_barcode({9: "ACTTGCGTT"}, catalog.ends["forward"], 0)
    assert match.status == "unknown"
    rule = extraction_rules(DemuxConfig(), catalog)["forward"]
    assert extract_barcode(b"AAGCTTGCGTT", rule, 9) == "AAGCTTGCG"


def test_sample_expectations_never_resolve_tie_or_unexpected_pair():
    catalog = load_catalog(bundled_catalog())
    forward = identify_barcode({9: "GCTTGCTTT"}, catalog.ends["forward"], 1)
    reverse = identify_barcode({9: "CTGTGTAGT"}, catalog.ends["reverse"], 1)
    assert assign_barcode_pair(forward, reverse, {("F1", "RB"): "1B"}) == ("ambiguous_barcode_match", None)
    forward = identify_barcode({9: "GCTTGTAGT"}, catalog.ends["forward"], 0)
    reverse = identify_barcode({9: "CTGTGCGTT"}, catalog.ends["reverse"], 0)
    assert assign_barcode_pair(forward, reverse, {("F2", "RC"): "2C"}) == ("unexpected_valid_barcode_pair", None)


def test_exact_is_preferred_to_more_distant_candidate():
    match = identify_barcode({4: "AAAA"}, {"F1": "AAAA", "F2": "AAAT"}, 1)
    assert match.barcode_id == "F1"


@pytest.mark.parametrize("kind", ["id", "sequence", "direction", "invalid_sequence", "missing_end"])
def test_bad_catalog_rejected(write_csv, kind):
    rows = [{"direction": "forward", "barcode_id": "F", "sequence": "ACGT"}, {"direction": "reverse", "barcode_id": "R", "sequence": "TGCA"}]
    if kind == "id":
        rows[1]["barcode_id"] = "F"
    elif kind == "sequence":
        rows.append(dict(rows[0], barcode_id="F2"))
    elif kind == "direction":
        rows[1]["direction"] = "R2"
    elif kind == "invalid_sequence":
        rows[0]["sequence"] = "ACGN"
    else:
        rows.pop()
    with pytest.raises(MetadataError):
        load_catalog(write_csv("catalog.csv", rows))


@pytest.mark.parametrize("kind", ["unknown", "wrong_end", "conflict"])
def test_id_definition_errors(write_csv, kind):
    row = {"sample_name": "sample", "barcode_id": "A", "forward_barcode_id": "F1", "reverse_barcode_id": "RB"}
    if kind == "unknown":
        row["forward_barcode_id"] = "F99"
    elif kind == "wrong_end":
        row["forward_barcode_id"] = "RA"
    else:
        row["forward_barcode"] = "AAAA"
    with pytest.raises(MetadataError):
        load_samples(write_csv("samples.csv", [row]), load_catalog(bundled_catalog()), metadata_required=False)


def test_catalog_additions_need_no_code_change(write_csv):
    rows = [{"direction": "forward", "barcode_id": "F13", "sequence": "GCTTAAAAT"},
            {"direction": "reverse", "barcode_id": "RI", "sequence": "CTGTAAAAT"}]
    catalog = load_catalog(write_csv("catalog.csv", rows))
    row = {"sample_name": "new", "barcode_id": "13I", "forward_barcode_id": "F13", "reverse_barcode_id": "RI"}
    sample = load_samples(write_csv("samples.csv", [row]), catalog, metadata_required=False)[0]
    assert sample.forward_barcode == "GCTTAAAAT"


def test_matching_explicit_and_catalog_definitions_are_allowed(write_csv):
    row = {"sample_name": "sample", "barcode_id": "A", "forward_barcode_id": "F1", "reverse_barcode_id": "RB", "forward_barcode": "gcttgcgtt", "reverse_barcode": ""}
    sample = load_samples(write_csv("samples.csv", [row]), load_catalog(bundled_catalog()), metadata_required=False)[0]
    assert sample.reverse_barcode == "CTGTGTAGT"


def test_explicit_custom_sequences_still_resolve(example_dir):
    catalog = Catalog([])
    samples = load_samples(example_dir / "samples.csv", catalog, metadata_required=False)
    assert len(samples) == 2
    assert samples[0].forward_barcode_id == "forward_AAAA"
    assert samples[0].biological_replicate == "1"


def test_custom_lengths_and_offset():
    catalog = Catalog([Barcode(direction="forward", barcode_id="F", sequence="ACG"), Barcode(direction="reverse", barcode_id="R", sequence="TGCAT")])
    rules = extraction_rules(DemuxConfig(profile="custom", forward_offset=2, forward_length=3, reverse_length=5), catalog)
    assert extract_barcode(b"TTACGCC", rules["forward"], 3) == "ACG"
    with pytest.raises(MetadataError, match="lengths disagree"):
        extraction_rules(DemuxConfig(), catalog)


def test_variable_length_prefix_tie_is_ambiguous():
    match = identify_barcode({3: "AAA", 5: "AAAAA"}, {"short": "AAA", "long": "AAAAA"}, 0)
    assert match.status == "ambiguous"


def test_trim_bridge_requires_a_bridge():
    catalog = load_catalog(bundled_catalog())
    with pytest.raises(MetadataError, match="configured forward bridge"):
        extraction_rules(DemuxConfig(profile="custom", trim_barcodes=True, trim_bridges=True), catalog)


@pytest.mark.parametrize("forward,reverse,category", [
    ("recognized", "recognized", "assigned_expected_pair"),
    ("recognized", "unknown", "forward_only"),
    ("unknown", "recognized", "reverse_only"),
    ("unknown", "unknown", "no_barcode_match"),
    ("ambiguous", "recognized", "ambiguous_barcode_match"),
    ("recognized", "ambiguous", "ambiguous_barcode_match"),
    ("ambiguous", "unknown", "ambiguous_barcode_match"),
    ("unknown", "ambiguous", "ambiguous_barcode_match"),
    ("ambiguous", "ambiguous", "ambiguous_barcode_match"),
])
def test_terminal_precedence_for_every_end_status(forward, reverse, category):
    result = assign_barcode_pair(BarcodeMatch(forward, "F1"), BarcodeMatch(reverse, "RB"), {("F1", "RB"): "1B"})
    assert result == (category, "1B" if category == "assigned_expected_pair" else None)
