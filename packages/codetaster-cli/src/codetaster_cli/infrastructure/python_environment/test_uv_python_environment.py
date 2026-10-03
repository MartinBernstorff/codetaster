from pathlib import Path

from codetaster_cli.domain.domain_model.checkout import CheckoutPath
from codetaster_cli.infrastructure.python_environment.uv_python_environment import (
    UvPythonEnvironment,
)


def test_removing_the_virtualenv_deletes_it(tmp_path: Path) -> None:
    (tmp_path / ".venv" / "bin").mkdir(parents=True)

    _ = UvPythonEnvironment().remove_virtualenv(CheckoutPath(tmp_path))

    assert not (tmp_path / ".venv").exists()
