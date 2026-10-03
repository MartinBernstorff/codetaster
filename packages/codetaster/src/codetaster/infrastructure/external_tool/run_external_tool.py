import logging
import shlex
import subprocess
from enum import Enum, auto
from typing import override

from pydantic import ConfigDict, RootModel
from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.tool_errors import (
    ExitCode,
    InstallationHint,
    ToolError,
    ToolFailedError,
    ToolInvocation,
    ToolNotFoundError,
)


class ToolArguments(RootModel[tuple[str, ...]]):
    """A program followed by its arguments, as passed to exec."""

    model_config = ConfigDict(frozen=True)

    def invocation(self) -> ToolInvocation:
        return ToolInvocation(shlex.join(self.root))

    @override
    def __str__(self) -> str:
        return shlex.join(self.root)

    @staticmethod
    def fake() -> ToolArguments:
        return ToolArguments(("true",))


class ToolOutput(RootModel[str]):
    """What a tool wrote to stdout, when captured."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> ToolOutput:
        return ToolOutput("")


class OutputMode(Enum):
    SHOW = auto()
    CAPTURE = auto()


def run_external_tool(
    arguments: ToolArguments,
    checkout: CheckoutPath,
    output_mode: OutputMode,
    hint: InstallationHint,
) -> Result[ToolOutput, ToolError]:
    """Run a tool inside `checkout`. Adapters share this; it is not a port.

    In `CAPTURE` mode, a failing tool's stdout and stderr are logged, since
    nothing else shows them.
    """
    capture = subprocess.PIPE if output_mode is OutputMode.CAPTURE else None
    try:
        completed = subprocess.run(
            arguments.root,
            cwd=checkout.root,
            stdout=capture,
            stderr=capture,
            text=True,
            check=False,
        )
    except FileNotFoundError as error:
        # Also raised for a missing cwd; only a missing program is expected.
        if error.filename != arguments.root[0]:
            raise
        return Err(ToolNotFoundError(arguments.invocation(), hint))
    if completed.returncode != 0:
        if output_mode is OutputMode.CAPTURE and (completed.stdout or completed.stderr):
            logging.getLogger(__name__).error(
                "`%s` failed.\nstdout:\n%s\nstderr:\n%s",
                arguments,
                completed.stdout,
                completed.stderr,
            )
        return Err(
            ToolFailedError(arguments.invocation(), ExitCode(completed.returncode))
        )
    return Ok(ToolOutput(completed.stdout or ""))
