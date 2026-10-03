from typing import override

from pydantic import ConfigDict, RootModel


class ToolInvocation(RootModel[str]):
    """An external tool call as a user would type it, e.g. `uv sync --locked`."""

    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return self.root

    @staticmethod
    def fake() -> ToolInvocation:
        return ToolInvocation("true")


class InstallationHint(RootModel[str]):
    """Tells the user how to get a missing tool onto PATH."""

    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return self.root

    @staticmethod
    def fake() -> InstallationHint:
        return InstallationHint("Install it, then re-run.")


class ExitCode(RootModel[int]):
    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return str(self.root)

    @staticmethod
    def fake() -> ExitCode:
        return ExitCode(1)


class ToolFailedError(Exception):
    def __init__(self, invocation: ToolInvocation, exit_code: ExitCode) -> None:
        super().__init__(f"`{invocation}` failed with exit code {exit_code}")
        self.invocation = invocation
        self.exit_code = exit_code

    @staticmethod
    def fake() -> ToolFailedError:
        return ToolFailedError(ToolInvocation.fake(), ExitCode.fake())


class ToolNotFoundError(Exception):
    def __init__(self, invocation: ToolInvocation, hint: InstallationHint) -> None:
        super().__init__(f"`{invocation}` failed: the program is not on PATH. {hint}")
        self.invocation = invocation

    @staticmethod
    def fake() -> ToolNotFoundError:
        return ToolNotFoundError(ToolInvocation.fake(), InstallationHint.fake())


type ToolError = ToolFailedError | ToolNotFoundError
