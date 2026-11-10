"""E09: adversarial official-template Excel import (unit under test: gui.sample_workbook.parse).

Usage: python exp_excel_import.py EVIDENCE_JSON
Workbooks are fabricated here with openpyxl / raw ZIP edits. Each case states the expected
outcome before the product is called. No science is executed by import.
"""
import io
import json
import sys
import zipfile
from pathlib import Path
from openpyxl import load_workbook, Workbook
from openpyxl.comments import Comment
from peanalyzer.gui.sample_workbook import parse, template, COLUMNS

cases = []


def base(rows, mutate=None, profile='qi_hitom_v1'):
    book = load_workbook(io.BytesIO(template()))
    sheet = book['Samples']
    header = [c.value for c in sheet[1]]
    for row in rows:
        sheet.append([row.get(h) for h in header])
    if mutate:
        mutate(book, sheet)
    out = io.BytesIO(); book.save(out)
    return out.getvalue()


def good(barcode='4A', name='s1', **over):
    row = dict(barcode_id=barcode, sample_name=name, editor='PE2', treatment='ctrl', dpi=7, biological_replicate='1')
    row.update(over)
    return row


def run(name, data, expect_ok, profile='qi_hitom_v1', expect=None, note=''):
    result = parse(data, profile)
    ok_import = not result['errors']
    passed = ok_import == expect_ok and (expect is None or expect(result))
    cases.append(dict(case=name, expected='ACCEPT' if expect_ok else 'REJECT', actual='ACCEPT' if ok_import else 'REJECT',
                      ok=passed, note=note, errors=[e['message'][:160] for e in result['errors']][:3],
                      samples=result['samples'][:3]))
    print(('PASS ' if passed else 'FAIL ') + name + ' -> ' + ('accepted' if ok_import else 'rejected: ' + '; '.join(e['message'][:90] for e in result['errors'][:2])))
    return result


run('baseline_two_rows', base([good('4A', 's1'), good('5B', 's2', biological_replicate='2')]), True,
    expect=lambda r: [s['forward_barcode'] for s in r['samples']] == ['GCTTCTCGT', 'GCTTGCTCT'] and [s['reverse_barcode'] for s in r['samples']] == ['CTGTGCGTT', 'CTGTGTAGT'])
run('formula_in_sample_name', base([good()], lambda b, s: s.cell(2, 2, '=A1')), False)
run('formula_in_dpi', base([good()], lambda b, s: s.cell(2, 5, '=3+4')), False)
run('formula_text_dde_like', base([good(name=None)], lambda b, s: s.cell(2, 2, '=cmd|"/c calc"!A1')), False)
run('hyperlink_cell', base([good()], lambda b, s: setattr(s.cell(2, 2), 'hyperlink', 'http://example.org')), False)
r = run('leading_zero_text_replicate_preserved', base([good(biological_replicate='007')]), True,
        expect=lambda r: r['samples'][0]['biological_replicate'] == '007')
r = run('numeric_replicate_becomes_integer_text', base([good(biological_replicate=7)]), True,
        expect=lambda r: r['samples'][0]['biological_replicate'] == '7',
        note='A numeric Excel cell cannot carry leading zeros; documented: use text cells for IDs.')
run('leading_zero_barcode_shorthand_rejected', base([good('04A')]), False)
run('numeric_barcode_id_rejected', base([good(4)]), False)
run('unknown_reverse_barcode', base([good('4Z')]), False)
run('unknown_forward_barcode', base([good('13A')]), False)
run('lowercase_shorthand_rejected', base([good('4a')]), False)
run('conflicting_explicit_catalog_id', base([good(forward_barcode_id='F5')]), False)
run('conflicting_explicit_sequence', base([good(forward_barcode='GCTTGCGTT')]), False)
run('redundant_matching_sequence_accepted', base([good(forward_barcode='GCTTCTCGT', reverse_barcode='CTGTGCGTT')]), True)
run('duplicate_barcode_rows', base([good('4A', 's1'), good('4A', 's2')]), False)
run('duplicate_sample_names', base([good('4A', 's1'), good('5A', 's1')]), False)
run('missing_dpi', base([good(dpi=None)]), False)
run('fractional_dpi', base([good(dpi=6.5)]), False)
run('float_integer_dpi_accepted', base([good(dpi=6.0)]), True, expect=lambda r: r['samples'][0]['dpi'] == '6')
run('negative_dpi', base([good(dpi=-1)]), False)
run('text_dpi_not_numeric', base([good(dpi='seven')]), False)
run('missing_replicate', base([good(biological_replicate=None)]), False)
run('missing_treatment', base([good(treatment=None)]), False)
import datetime
run('date_cell_in_replicate', base([good(biological_replicate=datetime.date(2026, 1, 2))]), False)
run('boolean_in_text_field', base([good(editor=True)]), False)
run('paired_true_without_block', base([good(paired=True)]), False)
run('paired_true_with_block', base([good(paired=True, block_id='leaf1')]), True, expect=lambda r: r['samples'][0]['paired'] is True)
run('paired_yes_text_not_inferred', base([good(paired='yes', block_id='leaf1')]), False)
run('paired_text_TRUE_case_insensitive', base([good(paired='TRUE', block_id='leaf1')]), True, expect=lambda r: r['samples'][0]['paired'] is True)
run('paired_numeric_1_not_inferred', base([good(paired=1, block_id='leaf1')]), False)
run('blank_row_inside_table', base([good('4A', 's1'), {}, good('5A', 's2')]), False)
run('trailing_blank_rows_ignored', base([good('4A', 's1'), {}, {}]), True)
run('whitespace_trimmed_at_cell_edges', base([good(name='  s1  ', editor=' PE2 ')]), True,
    expect=lambda r: r['samples'][0]['sample_name'] == 's1' and r['samples'][0]['editor'] == 'PE2')
run('sample_name_with_space_rejected', base([good(name='leaf 1')]), False)


def dup_header(b, s):
    s.cell(1, 7, 'editor')


run('duplicate_header', base([good()], dup_header), False)
run('unknown_header', base([good()], lambda b, s: s.cell(1, 12, 'genotype')), False)
run('missing_required_header', base([good()], lambda b, s: s.cell(1, 4, 'block_id2')), False)
run('hidden_row', base([good('4A', 's1'), good('5A', 's2')], lambda b, s: setattr(s.row_dimensions[3], 'hidden', True)), False)
run('hidden_column', base([good()], lambda b, s: setattr(s.column_dimensions['C'], 'hidden', True)), False)
run('merged_cells', base([good()], lambda b, s: s.merge_cells('A5:B5')), False)
run('extra_sheet', base([good()], lambda b, s: b.create_sheet('Extra')), False)
run('hidden_alternative_sheet_named_like_data', base([good()], lambda b, s: setattr(b.create_sheet('Samples2'), 'sheet_state', 'hidden')), False)


def defined_name(b, s):
    from openpyxl.workbook.defined_name import DefinedName
    b.defined_names['x'] = DefinedName('x', attr_text='Samples!$A$1')


run('named_range', base([good()], defined_name), False)
run('instructions_version_changed', base([good()], lambda b, s: b['Instructions'].cell(1, 1, 'PEAnalyzer sample template v2')), False)
run('thousand_and_one_rows', base([good(str(1 + i % 12) + 'ABCDEFGH'[i % 8], f's{i}') for i in range(1001)]), False)
run('not_a_zip', b'PK\x03\x04 this is not a workbook', False)
run('empty_bytes', b'', False)
data = base([good()])
# Raw-ZIP level attacks.
def rezip(data, transform):
    src = zipfile.ZipFile(io.BytesIO(data)); out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            payload = transform(item.filename, src.read(item.filename))
            if payload is not None:
                dst.writestr(item, payload)
        extra = transform(None, None)
        for name, payload in (extra or {}).items():
            dst.writestr(name, payload)
    return out.getvalue()
run('macro_part_added', rezip(data, lambda n, p: p if n else {'xl/vbaProject.bin': b'x'}), False)
run('external_link_part_added', rezip(data, lambda n, p: p if n else {'xl/externalLinks/externalLink1.xml': b'<a/>'}), False)
run('xml_entity_expansion_in_sheet', rezip(data, lambda n, p: (b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">]>' + p.split(b'?>', 1)[-1]) if n == 'xl/worksheets/sheet2.xml' else (p if n else None)), False)
run('truncated_xml', rezip(data, lambda n, p: p[:len(p) // 2] if n == 'xl/workbook.xml' else (p if n else None)), False)
big = rezip(data, lambda n, p: p if n else {'docProps/app.xml': b'<a>' + b'A' * (17 * 1024 * 1024) + b'</a>'})
run('expanded_archive_over_16MiB' if len(big) <= 2 * 1024 * 1024 else 'archive_over_2MiB', big, False)
# Custom profile: IDs without sequences are not guessed.
run('custom_profile_requires_sequences', base([good('X1', 's1')]), False, profile='custom')
run('custom_profile_with_sequences', base([good('X1', 's1', forward_barcode='ACGTAC', reverse_barcode='TGCATG')]), True, profile='custom')
run('custom_profile_non_acgt_sequence', base([good('X1', 's1', forward_barcode='ACGNNN', reverse_barcode='TGCATG')]), False, profile='custom')
# Biological-assumption probe: two rows, same condition, same biological_replicate (import must not merge them;
# authoritative duplicate-replicate rejection belongs to Validate & Review).
r = run('same_condition_same_replicate_import_keeps_both_rows', base([good('4A', 's1'), good('5A', 's2')]), True,
        expect=lambda r: len(r['samples']) == 2,
        note='Import is transport only; DUPLICATE_BIOLOGICAL_REPLICATE is raised by Validate & Review (checked in E10).')
summary = dict(experiment='E09_excel_import_adversarial', passed=sum(c['ok'] for c in cases), failed=sum(not c['ok'] for c in cases), cases=cases)
Path(sys.argv[1]).write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')
print(f"\n{summary['passed']} passed, {summary['failed']} failed")
