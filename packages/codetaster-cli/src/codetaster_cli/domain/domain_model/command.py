import shlex
from pathlib import Path
from typing import override

from pydantic import BaseModel, ConfigDict, RootModel


class CommandLine(RootModel[tuple[str, ...]]):
    """A program followed by its arguments, as passed to exec."""

    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return shlex.join(self.root)

    @staticmethod
    def fake() -> CommandLine:
        return CommandLine(("true",))


class WorkingDirectory(RootModel[Path]):
    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return str(self.root)

    @staticmethod
    def fake() -> WorkingDirectory:
        return WorkingDirectory(Path())


class Command(BaseModel):
    model_config = ConfigDict(frozen=True)

    line: CommandLine
    working_directory: WorkingDirectory

    @override
    def __str__(self) -> str:
        return f"`{self.line}` in {self.working_directory}"

    @staticmethod
    def fake() -> Command:
        return Command(
            line=CommandLine.fake(), working_directory=WorkingDirectory.fake()
        )


class CommandOutput(RootModel[str]):
    """What a command wrote to stdout."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> CommandOutput:
        return CommandOutput("")


class CommandCompleted(BaseModel):
    model_config = ConfigDict(frozen=True)

    command: Command

    @staticmethod
    def fake() -> CommandCompleted:
        return CommandCompleted(command=Command.fake())


class ExitCode(RootModel[int]):
    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return str(self.root)

    @staticmethod
    def fake() -> ExitCode:
        return ExitCode(1)


class CommandFailedError(Exception):
    def __init__(self, line: CommandLine, exit_code: ExitCode) -> None:
        super().__init__(f"`{line}` failed with exit code {exit_code}")
        self.line = line
        self.exit_code = exit_code


class ProgramNotFoundError(Exception):
    def __init__(self, line: CommandLine) -> None:
        super().__init__(f"`{line.root[0]}` was not found on PATH (running `{line}`)")
        self.line = line


type CommandError = CommandFailedError | ProgramNotFoundError
