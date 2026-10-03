from collections.abc import Mapping
from typing import override

from pydantic import RootModel
from safe_result import Ok, Result

from codetaster_cli.domain.domain_model.command import (
    Command,
    CommandCompleted,
    CommandError,
    CommandLine,
    CommandOutput,
)
from codetaster_cli.domain.secondary_ports.command_runner import CommandRunner


class ScriptedResults:
    """What the fake returns per command line. Unscripted commands succeed silently."""

    def __init__(
        self, results: Mapping[CommandLine, Result[CommandOutput, CommandError]]
    ) -> None:
        self._results = dict(results)

    def result_for(self, line: CommandLine) -> Result[CommandOutput, CommandError]:
        return self._results.get(line, Ok(CommandOutput.fake()))

    @staticmethod
    def fake() -> ScriptedResults:
        return ScriptedResults({})


class RecordedCommands(RootModel[list[Command]]):
    def lines(self) -> RecordedLines:
        return RecordedLines([command.line for command in self.root])

    @staticmethod
    def fake() -> RecordedCommands:
        return RecordedCommands([])


class RecordedLines(RootModel[list[CommandLine]]):
    @staticmethod
    def fake() -> RecordedLines:
        return RecordedLines([])


class FakeCommandRunner(CommandRunner):
    """Records every command instead of running it, and returns scripted results."""

    def __init__(self, scripted: ScriptedResults) -> None:
        self.scripted = scripted
        self.recorded = RecordedCommands.fake()

    @override
    def run_command(self, command: Command) -> Result[CommandCompleted, CommandError]:
        return self.capture_output(command).map(
            lambda _: CommandCompleted(command=command)
        )

    @override
    def capture_output(self, command: Command) -> Result[CommandOutput, CommandError]:
        self.recorded.root.append(command)
        return self.scripted.result_for(command.line)
