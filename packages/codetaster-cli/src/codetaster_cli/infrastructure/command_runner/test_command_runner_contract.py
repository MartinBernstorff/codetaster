from pathlib import Path

import pytest
from safe_result import Err, Ok

from codetaster_cli.domain.domain_model.command import (
    Command,
    CommandCompleted,
    CommandFailedError,
    CommandLine,
    CommandOutput,
    ExitCode,
    ProgramNotFoundError,
    WorkingDirectory,
)
from codetaster_cli.domain.secondary_ports.command_runner import CommandRunner
from codetaster_cli.infrastructure.command_runner.fake_command_runner import (
    FakeCommandRunner,
    ScriptedResults,
)
from codetaster_cli.infrastructure.command_runner.subprocess_command_runner import (
    SubprocessCommandRunner,
)


def _fake_scripted_like_a_shell() -> FakeCommandRunner:
    false = CommandLine(("false",))
    missing = CommandLine(("codetaster-no-such-program",))
    return FakeCommandRunner(
        ScriptedResults(
            {
                CommandLine(("echo", "hello")): Ok(CommandOutput("hello\n")),
                false: Err(CommandFailedError(false, ExitCode(1))),
                missing: Err(ProgramNotFoundError(missing)),
            }
        )
    )


@pytest.fixture(params=["subprocess", "fake"])
def runner(request: pytest.FixtureRequest) -> CommandRunner:
    if request.param == "subprocess":
        return SubprocessCommandRunner()
    return _fake_scripted_like_a_shell()


def test_run_command_succeeds_on_exit_code_zero(
    runner: CommandRunner, tmp_path: Path
) -> None:
    command = Command(
        line=CommandLine(("true",)), working_directory=WorkingDirectory(tmp_path)
    )

    assert runner.run_command(command) == Ok(CommandCompleted(command=command))


def test_run_command_reports_nonzero_exit_code(
    runner: CommandRunner, tmp_path: Path
) -> None:
    result = runner.run_command(
        Command(
            line=CommandLine(("false",)), working_directory=WorkingDirectory(tmp_path)
        )
    )

    assert result == Err(CommandFailedError(CommandLine(("false",)), ExitCode(1)))


def test_capture_output_returns_stdout(runner: CommandRunner, tmp_path: Path) -> None:
    result = runner.capture_output(
        Command(
            line=CommandLine(("echo", "hello")),
            working_directory=WorkingDirectory(tmp_path),
        )
    )

    assert result == Ok(CommandOutput("hello\n"))


def test_missing_program_is_reported_as_not_found(
    runner: CommandRunner, tmp_path: Path
) -> None:
    line = CommandLine(("codetaster-no-such-program",))

    result = runner.run_command(
        Command(line=line, working_directory=WorkingDirectory(tmp_path))
    )

    assert result == Err(ProgramNotFoundError(line))
