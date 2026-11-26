"""Native integer extraction, source binding and comparison are independent of PE eligibility."""
import json
from pathlib import Path
import shutil
import zipfile

import pytest

from peanalyzer.backend.native_artifacts import extract_native
from peanalyzer.backend.native_runs import write_native_runs, verify_native_runs
from peanalyzer.remediation import panel
from test_m4 import archive


@pytest.fixture
def native_cell(archive, tmp_path):
    cell = tmp_path/'cell'
    shutil.copytree(archive/'comparator', cell/'comparator')
    shutil.copytree(archive/'copies', cell/'copies')
    sample = json.loads((archive/'analysis/analysis_manifest.json').read_text())['samples']['1B']
    return cell, sample


def test_native_manifest_binds_population_commands_and_reference_assignment(native_cell):
    cell,sample = native_cell
    doc = write_native_runs(cell, '1B', 'test-target', panel(), sample)
    rows = {r['id']: r for r in doc['runs']}
    for copy in ('copy1','copy2'):
        row = rows['comparator/'+copy]
        assert row['population'] == 'all_prepared_pairs'
        assert row['input_pairs'] == row['counts']['backend_input_reads'] == 125
        assert (row['counts']['numerator'], row['counts']['denominator']) == (30,105)
        assert row['per_reference']['Prime-edited']['Reads_aligned'] == 30
        assert row['recount_status'] == 'PASS'
        # Archived test data did not perform a new runtime probe or replay.
        assert row['runtime_identity_status'] == 'UNVERIFIED' and row['direct_parity_status'] == 'NOT_RUN'
        assert rows['copies/'+copy]['population'] == 'confident_copy_cohort'
        assert rows['copies/'+copy]['input_pairs'] < 125
        assert [ref['name'] for ref in row['effective_references']][:2] == ['Reference','Prime-edited']
    assert doc == verify_native_runs(cell,'1B','test-target',panel(),sample)
    path = cell/rows['comparator/copy1']['paths']['script']
    path.write_text(path.read_text().replace('--amplicon_seq','--other'))
    with pytest.raises(ValueError,match='command changed'):
        verify_native_runs(cell,'1B','test-target',panel(),sample)


def test_recount_rejects_allele_event_changed_with_same_read_total(tmp_path):
    source=Path(__file__).resolve().parents[1]/'docs/validation/m8/backend/insertion_deletion'
    child=tmp_path/'native'
    shutil.copytree(source,child)
    info=child/'CRISPResso2_info.json'
    native=extract_native(info)
    assert native['per_reference']['Reference']['Insertions and Deletions'] > 0
    path=native['paths']['alleles']
    with zipfile.ZipFile(path) as archive:
        member,=archive.namelist()
        lines=archive.read(member).decode().splitlines()
    header=lines[0].split('\t')
    for i in range(1,len(lines)):
        fields=lines[i].split('\t')
        if int(fields[header.index('n_deleted')]) and int(fields[header.index('n_inserted')]):
            fields[header.index('n_deleted')]='0'
            lines[i]='\t'.join(fields)
            break
    with zipfile.ZipFile(path,'w') as archive:
        archive.writestr(member,'\n'.join(lines)+'\n')
    with pytest.raises(ValueError,match='recount disagrees'):
        extract_native(info)
