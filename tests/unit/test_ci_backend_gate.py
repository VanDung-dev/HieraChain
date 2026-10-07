"""A required backend job cannot succeed by skipping its contract tests."""

from types import SimpleNamespace

import pytest

from tests.conftest import pytest_sessionfinish


@pytest.mark.parametrize(("required", "skipped", "expected"), [(True, True, 1), (True, False, 0), (False, True, 0)])
def test_required_backend_skips_fail_the_session(required: bool, skipped: bool, expected: int) -> None:
    reporter = SimpleNamespace(stats={"skipped": [object()] if skipped else []})
    session = SimpleNamespace(exitstatus=0, config=SimpleNamespace(
        getoption=lambda name: required,
        pluginmanager=SimpleNamespace(getplugin=lambda name: reporter),
    ))
    pytest_sessionfinish(session, 0)
    assert session.exitstatus == expected
