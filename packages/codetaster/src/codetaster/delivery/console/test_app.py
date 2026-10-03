import logging

import pytest
from typer.testing import CliRunner

from codetaster.delivery.console.app import app


def test_hello_logs_greeting(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)

    result = CliRunner().invoke(app, ["hello"])

    assert result.exit_code == 0
    assert "Hello from codetaster" in caplog.messages
