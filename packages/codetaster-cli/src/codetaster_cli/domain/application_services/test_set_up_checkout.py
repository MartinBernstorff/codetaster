from safe_result import Err, Ok

from codetaster_cli.domain.application_services.set_up_checkout import set_up_checkout
from codetaster_cli.domain.domain_model.checkout import CheckoutPath
from codetaster_cli.domain.domain_model.tool_errors import ToolFailedError
from codetaster_cli.infrastructure.fakes.call_log import CallLog, RecordedCall
from codetaster_cli.infrastructure.git_hooks.fake_git_hooks import FakeGitHooks
from codetaster_cli.infrastructure.python_environment.fake_python_environment import (
    FakePythonEnvironment,
)
from codetaster_cli.infrastructure.toolchain.fake_toolchain import FakeToolchain


def test_installs_tools_then_dependencies_then_hooks() -> None:
    log = CallLog.fake()

    result = set_up_checkout(
        FakeToolchain(log),
        FakePythonEnvironment(log),
        FakeGitHooks(log),
        CheckoutPath.fake(),
    )

    assert result == Ok(CheckoutPath.fake())
    assert log == CallLog(
        [
            RecordedCall.INSTALL_PINNED_TOOLS,
            RecordedCall.SYNC_DEPENDENCIES,
            RecordedCall.INSTALL_HOOKS,
        ]
    )


def test_stops_at_the_first_failing_step() -> None:
    log = CallLog.fake()
    failure = ToolFailedError.fake()

    result = set_up_checkout(
        FakeToolchain(log),
        FakePythonEnvironment(log, failure),
        FakeGitHooks(log),
        CheckoutPath.fake(),
    )

    assert result == Err(failure)
    assert log == CallLog(
        [RecordedCall.INSTALL_PINNED_TOOLS, RecordedCall.SYNC_DEPENDENCIES]
    )
