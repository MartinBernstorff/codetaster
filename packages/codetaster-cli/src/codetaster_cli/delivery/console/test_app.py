import logging
from pathlib import Path

import pytest
from typer.testing import CliRunner

from codetaster_cli.delivery.console.app import app


def test_setup_without_proto_explains_how_to_install_it(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    caplog.set_level(logging.INFO)

    result = CliRunner().invoke(app, ["setup"])

    assert result.exit_code == 1
    assert any(
        "https://moonrepo.dev/docs/proto/install" in message
        for message in caplog.messages
    )
