from pathlib import Path

from safe_result import Err, Ok

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.tool_errors import (
    ExitCode,
    InstallationHint,
    ToolFailedError,
    ToolNotFoundError,
)
from codetaster.infrastructure.external_tool.run_external_tool import (
    OutputMode,
    ToolArguments,
    ToolOutput,
    run_external_tool,
)


def test_captures_stdout_of_a_successful_tool(tmp_path: Path) -> None:
    message = "hello"

    result = run_external_tool(
        ToolArguments(("echo", message)),
        CheckoutPath(tmp_path),
        OutputMode.CAPTURE,
        InstallationHint.fake(),
    )

    assert result == Ok(ToolOutput(f"{message}\n"))


def test_reports_the_exit_code_of_a_failing_tool(tmp_path: Path) -> None:
    failure_exit_code = ExitCode(1)

    result = run_external_tool(
        ToolArguments(("false",)),
        CheckoutPath(tmp_path),
        OutputMode.SHOW,
        InstallationHint.fake(),
    )

    assert isinstance(result, Err)
    assert isinstance(result.error, ToolFailedError)
    assert result.error.exit_code == failure_exit_code


def test_reports_a_missing_program_with_the_installation_hint(tmp_path: Path) -> None:
    hint = InstallationHint.fake()

    result = run_external_tool(
        ToolArguments(("codetaster-no-such-program",)),
        CheckoutPath(tmp_path),
        OutputMode.SHOW,
        hint,
    )

    assert isinstance(result, Err)
    assert isinstance(result.error, ToolNotFoundError)
    assert str(hint) in str(result.error)
