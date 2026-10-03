from typing import Protocol

from safe_result import Result

from codetaster_cli.domain.domain_model.command import (
    Command,
    CommandCompleted,
    CommandError,
    CommandOutput,
)


class CommandRunner(Protocol):
    def run_command(self, command: Command) -> Result[CommandCompleted, CommandError]:
        """Run `command`, letting it write straight to the terminal."""
        ...

    def capture_output(self, command: Command) -> Result[CommandOutput, CommandError]:
        """Run `command` and return its stdout instead of printing it."""
        ...
