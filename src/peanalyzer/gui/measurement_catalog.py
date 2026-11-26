"""Attach verified artifact handles to staged measurements and native runs."""
from peanalyzer.gui.models import MeasurementRow, NativeRunView, RunFile
from peanalyzer.gui.scientific_projection import diagnostic_fields
from peanalyzer.workflow_storage import WorkflowError


def project_catalog(cell, result, read, sources):
    doc = read(cell+'/measurements.json')
    native = read(cell+'/native_runs.json')
    identity = (result.sample_id, result.target_id)
    if (doc['contract'] != 'measurement-catalog-v1' or (doc['sample_id'], doc['target']) != identity or
            (native['sample_id'],native['target_name']) != identity):
        raise WorkflowError('SOURCE_IDENTITY_MISMATCH','Measurement catalog identity differs')
    rows = []
    for item in doc['rows']:
        row = dict(item)
        row['copy_name'] = row.pop('copy')
        path = cell+'/'+row['source_artifact']
        if path not in sources or sources[path].sha256 != row['source_sha256']:
            raise WorkflowError('SOURCE_IDENTITY_MISMATCH','Measurement row source differs')
        for field in ('integer_count','numerator','denominator'):
            if row[field] is not None:
                row[field] = str(row[field])
        rows.append(MeasurementRow(**row))
    runs = []
    for item in native['runs']:
        files = []
        for role,name in item['paths'].items():
            source = sources.get(cell+'/'+name)
            expected = item['sha256'].get(role)
            if source is None or (expected is not None and source.sha256 != expected):
                raise WorkflowError('SOURCE_IDENTITY_MISMATCH','Native execution artifact differs')
            files.append(RunFile(role=role,source=source))
        keys = ('copy','input_pairs','physical_mate_order','original_reference','effective_references','include_idxs',
                'version','argv','required_image','runtime_identity_status','reasons')
        runs.append(NativeRunView(sample_id=result.sample_id,target=result.target_id,run_id=item['id'],
            mode=item['mode'],population=item['population'],execution=item['execution_status'],
            extraction=item['extraction_status'],recount=item['recount_status'],direct_parity=item['direct_parity_status'],
            evidence=diagnostic_fields({k:item[k] for k in keys if k in item}),files=files))
    return rows, runs
