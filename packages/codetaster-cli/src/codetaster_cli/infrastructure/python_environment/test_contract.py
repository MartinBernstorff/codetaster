"""Contract for PythonEnvironment, run against every implementation."""

from pathlib import Path

import pytest
from safe_result import Ok

from codetaster_cli.domain.domain_model.checkout import CheckoutPath
from codetaster_cli.domain.secondary_ports.python_environment import (
    PythonEnvironment,
)
from codetaster_cli.infrastructure.fakes.call_log import CallLog
from codetaster_cli.infrastructure.python_environment.fake_python_environment import (
    FakePythonEnvironment,
)
from codetaster_cli.infrastructure.python_environment.uv_python_environment import (
    UvPythonEnvironment,
)


@pytest.fixture(params=["uv", "fake"])
def environment(request: pytest.FixtureRequest) -> PythonEnvironment:
    if request.param == "uv":
        return UvPythonEnvironment()
    return FakePythonEnvironment(CallLog.fake())


def test_removing_a_missing_virtualenv_succeeds(
    environment: PythonEnvironment, tmp_path: Path
) -> None:
    assert environment.remove_virtualenv(CheckoutPath(tmp_path)) == Ok(None)


def test_removing_an_existing_virtualenv_succeeds(
    environment: PythonEnvironment, tmp_path: Path
) -> None:
    (tmp_path / ".venv" / "bin").mkdir(parents=True)

    assert environment.remove_virtualenv(CheckoutPath(tmp_path)) == Ok(None)
