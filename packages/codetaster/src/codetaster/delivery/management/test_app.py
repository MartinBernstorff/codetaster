import logging
from pathlib import Path

import pytest
from typer.testing import CliRunner

from codetaster.delivery.management.app import app


def test_setup_without_proto_explains_how_to_install_it(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    failure_exit_code = 1
    proto_install_instructions = "https://moonrepo.dev/docs/proto/install"
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    caplog.set_level(logging.INFO)

    result = CliRunner().invoke(app, ["setup"])

    assert result.exit_code == failure_exit_code
    assert any(proto_install_instructions in message for message in caplog.messages)
