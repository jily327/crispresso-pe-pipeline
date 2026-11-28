"""Matched-population exploratory comparisons of stored TIGR window outcomes."""
import hashlib
from pathlib import Path

from peanalyzer.nuclease.models import MulticopyNucleaseResult, NucleaseMetricResult, observation_populations
from peanalyzer.result_dispatch import metric_model
from peanalyzer.aggregation import strict_json


def compare(primary, exploratory):
    entries = []
    identity = None
    for path, is_primary in ((primary,True),(exploratory,False)):
        data = Path(path).read_bytes()
        raw = strict_json(data)
        model = metric_model(raw)
        if model not in (NucleaseMetricResult, MulticopyNucleaseResult):
            raise ValueError('Window comparison requires a measured nuclease result')
        metric = model.model_validate(raw)
        targets = metric.targets if isinstance(metric,MulticopyNucleaseResult) else [metric.target]
        window_names = {t.tigr_window for t in targets}
        allowed = {'W2'} if is_primary else {'W1','W3','W4'}
        if len(window_names) != 1 or not window_names <= allowed or any(t.nuclease_profile!='tigr_tas_v1' for t in targets):
            raise ValueError('Select primary TIGR W2 and a distinct exploratory TIGR window')
        prepared = metric.provenance.prepared_sample
        panel_identity = (metric.sample_id, metric.target_id, metric.identity_mechanism,
            {t.copy_name:t.model_dump(exclude={'tigr_window'}) for t in targets},
            prepared['pairs'], {mate:entry['sha256'] for mate,entry in prepared['files'].items()},
            metric.provenance.crispresso_version, metric.provenance.runtime_digest)
        if identity is not None and panel_identity != identity:
            raise ValueError('Window comparison requires the same sample, prepared reads, references and caller')
        identity = panel_identity
        entries.append(dict(role='primary' if is_primary else 'exploratory',window=window_names.pop(),
            source_sha256=hashlib.sha256(data).hexdigest(),windows={t.copy_name:t.window for t in targets},
            indel_fractions=[dict(copy_name=copy,**group.metrics['indel_fraction'].model_dump(),
                                  status=group.status,reason_codes=group.reason_codes)
                             for copy,group in observation_populations(metric).items()]))
    return dict(contract='tigr-window-comparison-v1',analysis='exploratory_window_comparison',
                sample_id=identity[0],target_name=identity[1],primary_window='W2',measurements=entries)
