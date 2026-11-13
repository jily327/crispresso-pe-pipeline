"""Executable aliases must retain canonical backend and recovery identity."""
import shutil
import pytest
from test_m7 import case
from test_m11c_recovery import partial, client_for, open_preview
from peanalyzer.gui.recovery import inspect
from peanalyzer.gui.execution import RuntimeSettings
from peanalyzer.workflow_recovery import workspace_identity
from peanalyzer.workflow_storage import WorkflowError


def test_executable_alias_matches_stored_canonical_identity(case, tmp_path):
    options, _ = partial(case)
    alias = tmp_path/'installed-alias'; alias.symlink_to(options['crispresso'])
    direct, direct_preflight, _ = inspect(options['output'], RuntimeSettings(crispresso=options['crispresso']))
    resolved, preflight, status = inspect(options['output'], RuntimeSettings(crispresso=str(alias)))
    assert status=='RESUMABLE' and resolved==direct and preflight==direct_preflight


def test_alias_retarget_after_preview_never_executes_or_deletes(case, tmp_path):
    options, _ = partial(case)
    alias = tmp_path/'installed-alias'; alias.symlink_to(options['crispresso'])
    app, client = client_for({**options, 'crispresso':str(alias)})
    view = open_preview(client)
    assert view['classification']=='RESUMABLE'
    before = workspace_identity(options['output'])
    # Even identical bytes at a different canonical path are a different backend.
    other = tmp_path/'redirected'; shutil.copy2(options['crispresso'], other)
    alias.unlink(); alias.symlink_to(other)
    response = client.post(f"/api/v1/recovery/{view['recovery_id']}/execute", json=dict(
        revision=view['revision'], recovery_plan_sha256=view['recovery_plan_sha256'], confirmed=True))
    assert response.status_code==409
    assert not app.state.jobs.jobs
    assert workspace_identity(options['output'])==before


def test_executable_alias_does_not_allow_workspace_alias(case, tmp_path):
    options, _ = partial(case)
    alias = tmp_path/'workspace-alias'; alias.symlink_to(options['output'], target_is_directory=True)
    before = workspace_identity(options['output'])
    with pytest.raises(WorkflowError, match='UNSAFE_PATH'):
        inspect(alias, RuntimeSettings(crispresso=options['crispresso']))
    assert workspace_identity(options['output'])==before
