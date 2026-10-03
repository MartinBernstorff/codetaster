"""Contract for PythonEnvironment, run against every implementation."""

import subprocess
from pathlib import Path

import pytest
from safe_result import Ok

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.secondary_ports.python_environment import (
    PythonEnvironment,
)
from codetaster.infrastructure.python_environment.fake_python_environment import (
    FakePythonEnvironment,
)
from codetaster.infrastructure.python_environment.uv_python_environment import (
    UvPythonEnvironment,
)


@pytest.fixture(params=["uv", "fake"])
def environment(request: pytest.FixtureRequest) -> PythonEnvironment:
    if request.param == "uv":
        return UvPythonEnvironment()
    return FakePythonEnvironment()


@pytest.fixture
def locked_project(tmp_path: Path) -> CheckoutPath:
    _ = (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "contract"\nversion = "0"\nrequires-python = ">=3.14"\n'
    )
    _ = subprocess.run(["uv", "lock", "--quiet"], cwd=tmp_path, check=True)
    return CheckoutPath(tmp_path)


def test_syncing_a_locked_project_succeeds(
    environment: PythonEnvironment, locked_project: CheckoutPath
) -> None:
    assert environment.sync_dependencies(locked_project) == Ok(None)
    assert environment.sync_dependencies(locked_project) == Ok(None)
