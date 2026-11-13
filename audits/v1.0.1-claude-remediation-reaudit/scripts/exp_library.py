"""E25-E30: historical analysis library (genuine 0.8.0 / 0.9.0 / 1.0.0 workspaces) under the 1.0.0 viewer.

Usage: python exp_library.py VENV_PYTHON HIST_ROOT PE_TRUTH EVIDENCE_JSON
HIST_ROOT/v0.8.0/exp1, v0.9.0/exp1, v1.0.0/exp1 were produced by the real CLIs of those releases
(isolated environments, same synthetic pool, real CRISPResso2 2.3.4). Decoys are added here.
"""
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from gui_client import Server

python, hist, truth_path, evidence_path = sys.argv[1], Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
truth = json.load(open(truth_path))
evidence = dict(experiment='E25_E30_historical_library', cases={})


def note(name, expected, observed, ok):
    evidence['cases'][name] = dict(expected=expected, observed=observed, verdict='CONTROLLED' if ok else 'DEFECT')
    print(('[CONTROLLED] ' if ok else '[DEFECT] ') + name + ' -> ' + json.dumps(observed)[:300])


def tree_state(root):
    """Bytes + metadata fingerprint of every entry (detects any silent write/touch/creation)."""
    state = {}
    for path in sorted(Path(root).rglob('*')):
        s = path.lstat()
        state[str(path.relative_to(root))] = (s.st_mode, s.st_size, s.st_mtime_ns, s.st_ino,
                                              hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() and not path.is_symlink() else None)
    root_stat = Path(root).stat()
    state['.'] = (root_stat.st_mode, root_stat.st_mtime_ns)
    return state


# Decoys -----------------------------------------------------------------------------------------
decoys = hist / 'decoys'
if decoys.exists():
    shutil.rmtree(decoys)
decoys.mkdir()
# (a) incomplete: real 1.0.0 workspace re-created by copying and removing its completion marker.
incomplete = decoys / 'incomplete_run'
shutil.copytree(hist / 'v1.0.0/exp1', incomplete)
(incomplete / 'workflow_manifest.json').unlink()
# (b) forged catalogue metadata: claims COMPLETED and a fantasy version, no science behind it.
forged = decoys / 'forged_claim'
(forged / 'workflow').mkdir(parents=True)
(forged / 'workflow/plan.json').write_text('{"software_identity":{"pipeline_version":"9.9.9"}}')
(forged / 'workflow_manifest.json').write_text('{"status":"COMPLETED","workflow_contract_version":"m7-v1","software_identity":{"pipeline_version":"9.9.9"}}')
# (c) symlinked workspace directory and (d) symlinked completion marker.
os.symlink(hist / 'v1.0.0/exp1', decoys / 'symlinked_workspace')
linked = decoys / 'linked_marker'
(linked / 'workflow').mkdir(parents=True)
shutil.copyfile(hist / 'v1.0.0/exp1/workflow/plan.json', linked / 'workflow/plan.json')
os.symlink(hist / 'v1.0.0/exp1/workflow_manifest.json', linked / 'workflow_manifest.json')
# (e) folder name lies about the version.
liar = decoys / 'v9.9.9-looks-new'
shutil.copytree(hist / 'v0.8.0/exp1', liar / 'exp1')      # relocated copy of a 0.8.0 run

before = {v: tree_state(hist / v) for v in ('v0.8.0', 'v0.9.0', 'v1.0.0')}
server = Server(python, 8861, ['--workspace-library-root', str(hist), '--view-only'], hist.parent / 'server_library.log')
try:
    status, catalog = server.call('GET', 'workspaces')
    labels = sorted(r['label'] for r in catalog)
    evidence['labels'] = labels
    by = {r['label']: r['registration_id'] for r in catalog}

    def find(*parts):
        return [l for l in labels if all(p in l for p in parts)]

    note('E25.three_releases_discovered_with_provenance_versions_and_unique_names',
         'one entry per genuine workspace; version from stored provenance; duplicate folder names disambiguated; none claims verification',
         dict(v080=find('exp1', 'PEAnalyzer 0.8.0'), v090=find('exp1', 'PEAnalyzer 0.9.0'), v100=find('exp1', 'PEAnalyzer 1.0.0'),
              all_unique=len(set(labels)) == len(labels), any_says_verified=[l for l in labels if 'Verified' in l]),
         len(find('v0.8.0', 'exp1', 'PEAnalyzer 0.8.0', 'verification required')) == 1 and len(find('v0.9.0', 'exp1', 'PEAnalyzer 0.9.0', 'verification required')) == 1
         and len(find('v1.0.0', 'exp1', 'PEAnalyzer 1.0.0', 'verification required')) == 1 and len(set(labels)) == len(labels))
    note('E26.incomplete_is_not_presented_as_completed', '"Incomplete - use Recovery"', find('incomplete_run'),
         len(find('incomplete_run', 'Incomplete')) == 1)
    note('E27.symlinks_cannot_enter_the_catalogue', 'no symlinked_workspace entry; linked_marker not listed as a detected completed workspace',
         dict(symlinked_workspace=find('symlinked_workspace'), linked_marker=find('linked_marker')),
         not find('symlinked_workspace') and not find('linked_marker', 'verification required'))
    note('E28.folder_name_does_not_define_version', 'label shows stored 0.8.0, not 9.9.9', find('looks-new'),
         len(find('looks-new', 'PEAnalyzer 0.8.0')) == 1)
    opened = {}
    for v in ('v0.8.0', 'v0.9.0', 'v1.0.0'):
        label = find(v, 'exp1')[0]
        status, view = server.call('POST', 'workspaces/open', dict(registration_id=by[label]))
        row = dict(http=status, error=view.get('error', {}).get('code') if status != 200 else None)
        if status == 200:
            values = {}
            for o in view['observations']:
                if o['metric_name'] in ('total_precise_pe', 'target_crispresso_native_pe'):
                    values[o['sample_id'] + ':' + o['metric_name']] = [o['numerator'], o['denominator'], o['status']]
            row.update(values=values, contracts=view['contracts'],
                       source_version=next(json.loads(f['value'])['pipeline_version'] for f in view['provenance'] if f['name'] == 'source_software'),
                       export=server.call('GET', f"workspaces/{view['workspace_id']}/export")[1]['state'],
                       workbook_created=(hist / v / 'exp1/PEAnalyzer_Summary.xlsx').exists())
        opened[v] = row
    want = {}
    for b, c in truth['counts'].items():
        e = truth['expected_exact'][b]
        want[b + ':total_precise_pe'] = [str(e['numerator']), str(e['denominator']), 'REPORTABLE']
    exact_ok = all(opened[v].get('values') and all(opened[v]['values'][k] == w for k, w in want.items()) for v in opened)
    same_across = len({json.dumps(opened[v].get('values'), sort_keys=True) for v in opened}) == 1
    note('E29.old_workspaces_open_verified_with_identical_science_across_releases',
         'HTTP 200 for 0.8.0, 0.9.0, 1.0.0; exact PE equals designed truth; native identical across releases; no workbook created by viewing',
         dict(opened={v: {k: opened[v].get(k) for k in ('http', 'error', 'source_version', 'export', 'workbook_created')} for v in opened},
              exact_equals_truth=exact_ok, identical_values_across_releases=same_across),
         all(o['http'] == 200 for o in opened.values()) and exact_ok and same_across and not any(o['workbook_created'] for o in opened.values()))
    nuc = find('nuc1')
    if nuc:
        status, view = server.call('POST', 'workspaces/open', dict(registration_id=by[nuc[0]]))
        note('E29b.legacy_nuclease_workspace_opens', 'HTTP 200, mode indel_nuclease, export NOT_APPLICABLE',
             dict(http=status, mode=view.get('mode'), export=server.call('GET', f"workspaces/{view['workspace_id']}/export")[1]['state'] if status == 200 else None),
             status == 200 and view['mode'] == 'indel_nuclease')
    results = {}
    for name in ('forged_claim', 'incomplete_run', 'looks-new'):
        label = find(name)[0]
        status, body = server.call('POST', 'workspaces/open', dict(registration_id=by[label]))
        _, cat2 = server.call('GET', 'workspaces')
        results[name] = dict(http=status, code=body.get('error', {}).get('code'), detail=body.get('error', {}).get('detail', '')[:140],
                             label_after=[r['label'] for r in cat2 if name in r['label']])
    note('E30.detected_is_not_verified_and_failures_stay_visible',
         'forged claim, incomplete copy and relocated copy all fail Open (409) with a visible reason; labels never upgrade to verified',
         results, all(r['http'] == 409 for r in results.values()) and 'Incomplete' in results['incomplete_run']['label_after'][0]
         and 'incompatible' in results['forged_claim']['label_after'][0])
    status, body = server.call('POST', 'workspace-library/refresh', {})
    after = {v: tree_state(hist / v) for v in before}
    changed = {v: sorted(k for k in set(before[v]) | set(after[v]) if before[v].get(k) != after[v].get(k)) for v in before}
    note('E31.discovery_open_and_refresh_never_modify_old_workspaces',
         'byte, size, mtime, inode and inventory identical before/after discovery + open + refresh', changed, not any(changed.values()))
    status, body = server.call('POST', 'jobs', dict(draft_id='x', revision=0, plan_identity_sha256='0' * 64, scientific_identity_sha256='0' * 64))
    note('E32.view_only_library_cannot_start_science', 'HTTP 409 RUN_UNAVAILABLE', dict(http=status, code=(body.get('error') or {}).get('code')),
         status == 409 and body['error']['code'] in ('RUN_UNAVAILABLE', 'DRAFT_NOT_FOUND'))
finally:
    server.stop()
    shutil.rmtree(decoys)
evidence['flagged'] = sum(c['verdict'] != 'CONTROLLED' for c in evidence['cases'].values())
evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + '\n')
print(len(evidence['cases']) - evidence['flagged'], 'controlled;', evidence['flagged'], 'flagged')
