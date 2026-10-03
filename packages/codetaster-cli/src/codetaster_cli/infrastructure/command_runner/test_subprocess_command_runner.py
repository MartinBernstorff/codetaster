from pathlib import Path

from safe_result import Ok

from codetaster_cli.domain.domain_model.command import (
    Command,
    CommandLine,
    CommandOutput,
    WorkingDirectory,
)
from codetaster_cli.infrastructure.command_runner.subprocess_command_runner import (
    SubprocessCommandRunner,
)


def test_runs_in_the_working_directory(tmp_path: Path) -> None:
    command = Command(
        line=CommandLine(("pwd", "-P")), working_directory=WorkingDirectory(tmp_path)
    )

    result = SubprocessCommandRunner().capture_output(command)

    assert result == Ok(CommandOutput(f"{tmp_path.resolve()}\n"))
