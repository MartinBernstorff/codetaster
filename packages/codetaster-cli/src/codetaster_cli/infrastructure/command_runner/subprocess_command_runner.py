import subprocess
from enum import Enum, auto
from typing import override

from safe_result import Err, Ok, Result

from codetaster_cli.domain.domain_model.command import (
    Command,
    CommandCompleted,
    CommandError,
    CommandFailedError,
    CommandOutput,
    ExitCode,
    ProgramNotFoundError,
)
from codetaster_cli.domain.secondary_ports.command_runner import CommandRunner


class _Stdout(Enum):
    INHERIT = auto()
    CAPTURE = auto()


class SubprocessCommandRunner(CommandRunner):
    @override
    def run_command(self, command: Command) -> Result[CommandCompleted, CommandError]:
        return self._run(command, _Stdout.INHERIT).map(
            lambda _: CommandCompleted(command=command)
        )

    @override
    def capture_output(self, command: Command) -> Result[CommandOutput, CommandError]:
        return self._run(command, _Stdout.CAPTURE)

    def _run(
        self, command: Command, stdout: _Stdout
    ) -> Result[CommandOutput, CommandError]:
        try:
            completed = subprocess.run(
                command.line.root,
                cwd=command.working_directory.root,
                stdout=subprocess.PIPE if stdout is _Stdout.CAPTURE else None,
                text=True,
                check=False,
            )
        except FileNotFoundError as error:
            # Also raised for a missing cwd; only a missing program is expected.
            if error.filename != command.line.root[0]:
                raise
            return Err(ProgramNotFoundError(command.line))
        if completed.returncode != 0:
            return Err(CommandFailedError(command.line, ExitCode(completed.returncode)))
        return Ok(CommandOutput(completed.stdout or ""))
