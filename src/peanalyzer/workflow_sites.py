"""Versioned supplementary site measurements on one verified prepared sample."""
import json
from pathlib import Path

from peanalyzer.analysis_verify import verify_analysis_output
from peanalyzer.backend.intended_sites import run_core_sites
from peanalyzer.backend.pooled import BackendError
from peanalyzer.demux_verify import VerifiedSample, read_json, sha256_file
from peanalyzer.haplotypes import FLANK, MARKER_LENGTH, MIN_PHRED, STATES, build_panel, measure_sample
from peanalyzer.site_exports import verify_site_exports, write_site_exports


CONTRACT = 'intended-sites-v1.1'


def two_substitutions(targets):
    return any(len(t.wt_sequence) == len(t.prime_edited_sequence) and
               sum(a != b for a, b in zip(t.wt_sequence, t.prime_edited_sequence)) == 2
               for t in targets)


def write_workflow_sites(*, analysis_root, sample_id, targets, output, core, runtime_digest):
    if not two_substitutions(targets):
        return
    verified = verify_analysis_output(analysis_root)
    row = verified.manifest['samples'][sample_id]
    if row['pairs'] == 0:
        return
    files = row['files']
    sample = VerifiedSample(sample_id, row['pairs'],
                            *(verified.root / files[m]['path'] for m in ('r1', 'r2')),
                            *(files[m]['sha256'] for m in ('r1', 'r2')))
    doc = dict(contract=CONTRACT, sample_id=sample_id, target_name=targets[0].target_name,
               input_pairs=sample.pairs, backend_input_order='Acquired physical R1 then R2 after configured leading trims',
               prepared_manifest_sha256=verified.manifest_sha256,
               analysis_trim_5p=[verified.manifest[f'r{mate}_analysis_trim_5p'] for mate in (1, 2)])
    copies = {t.copy_name: {'WT': t.wt_sequence, 'PE': t.prime_edited_sequence} for t in targets}
    try:
        panel = build_panel(doc['target_name'], copies)
    except ValueError as exc:
        doc.update(status='BLOCKED', reason_codes=['UNQUALIFIED_SITE_CORRESPONDENCE'], diagnostic=str(exc))
    else:
        result = measure_sample(sample, panel, (0, 0), False)
        # Sample roles belong to the workflow inventory; this API receives prepared molecules only.
        result.pop('declared_negative_control')
        doc.update(result, site_coordinates_0based=panel.sites, copy_marker_starts_0based=list(panel.marker_starts),
                   reference_panel_sha256=panel.sha256, site_flank_length=FLANK, site_min_phred=MIN_PHRED,
                   copy_marker_length=MARKER_LENGTH)
        if sample.pairs:
            try:
                doc['backend'] = run_core_sites(targets=targets, r1=sample.r1, r2=sample.r2,
                                                input_pairs=sample.pairs, core=core, runtime_digest=runtime_digest,
                                                output=output / 'core_sites')
            except (ValueError, BackendError, OSError) as exc:
                doc['backend'] = dict(status='BLOCKED', reason_codes=[getattr(exc, 'code', 'SITE_BACKEND_UNAVAILABLE')],
                                      diagnostic=str(exc))
    with (output / 'intended_sites.json').open('x') as handle:
        json.dump(doc, handle, indent=2, allow_nan=False)
        handle.write('\n')
    write_site_exports(output, doc)


def verify_workflow_sites(output, result, targets):
    """Reconcile the supplementary populations and replay the source-bound exports."""
    path = Path(output) / 'intended_sites.json'
    artifact = result.provenance.artifacts.get(path.name)
    if (artifact is None or path.is_symlink() or artifact.sha256 != sha256_file(path)
            or artifact.size_bytes != path.stat().st_size):
        raise ValueError('Unbound site measurement')
    raw = read_json(path)
    if (raw['contract'] != CONTRACT or raw['sample_id'] != result.sample_id or raw['target_name'] != result.target_id
            or raw['prepared_manifest_sha256'] != result.provenance.prepared_manifest_sha256
            or raw['input_pairs'] != result.qc.prepared_input_reads):
        raise ValueError('Site analysis lineage mismatch')
    if raw['status'] != 'BLOCKED':
        copies = {t.copy_name: {'WT': t.wt_sequence, 'PE': t.prime_edited_sequence} for t in targets}
        panel = build_panel(result.target_id, copies)
        expected = dict(reference_panel_sha256=panel.sha256, site_coordinates_0based=panel.sites,
                        copy_marker_starts_0based=list(panel.marker_starts), site_flank_length=FLANK,
                        site_min_phred=MIN_PHRED, copy_marker_length=MARKER_LENGTH)
        if any(raw.get(key) != value for key, value in expected.items()):
            raise ValueError('Site panel, markers or sequencing policy do not match supplied targets')
        for method in ('two_site_q30', 'full_templates'):
            group = raw[method]
            if set(group['copies']) != {t.copy_name for t in targets}:
                raise ValueError('Incomplete copy inventory in site counts')
            partitions = [*group['copies'].values(), group['unresolved_copy']]
            for state in STATES:
                if sum(v['counts'][state] for v in partitions) != group['combined']['counts'][state]:
                    raise ValueError('Site copy partitions do not reconcile')
            for v in [*partitions, group['combined']]:
                if v['assessable'] != sum(v['counts'].values()) or v['assessable'] > raw['input_pairs']:
                    raise ValueError('Site-assessable population mismatch')
        if (sum(raw['site_exclusions'].values()) + raw['two_site_q30']['combined']['assessable'] != raw['input_pairs']
                or raw['full_template_exclusions'] + raw['full_templates']['combined']['assessable'] != raw['input_pairs']):
            raise ValueError('Site analysis exclusions do not reconcile')
        backend = raw.get('backend', {})
        if backend.get('status') in ('REPORTABLE', 'NOT_ASSESSABLE'):
            from peanalyzer.backend.intended_sites import read_core_sites
            recomputed = read_core_sites(Path(output) / 'core_sites' / 'CRISPResso_on_sites', targets,
                                         expected_input_pairs=raw['input_pairs'])
            execution = backend.get('execution', {})
            files = result.provenance.prepared_sample['files']
            if (execution.get('input_sha256') != [files[m]['sha256'] for m in ('r1', 'r2')]
                    or execution.get('runtime_digest') != result.provenance.runtime_digest
                    or execution.get('return_code') != 0 or
                    recomputed != {key: value for key, value in backend.items() if key != 'execution'}):
                raise ValueError('Supplementary site counts differ from the backend allele artifact')
    verify_site_exports(output, raw)
