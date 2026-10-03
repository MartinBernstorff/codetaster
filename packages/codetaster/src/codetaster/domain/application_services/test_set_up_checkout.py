from safe_result import Err, Ok

from codetaster.domain.application_services.set_up_checkout import set_up_checkout
from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.tool_errors import ToolFailedError
from codetaster.infrastructure.git_hooks.fake_git_hooks import FakeGitHooks
from codetaster.infrastructure.python_environment.fake_python_environment import (
    FakePythonEnvironment,
)
from codetaster.infrastructure.toolchain.fake_toolchain import FakeToolchain


def test_sets_up_tools_dependencies_and_hooks() -> None:
    checkout = CheckoutPath.fake()
    toolchain = FakeToolchain()
    environment = FakePythonEnvironment()
    hooks = FakeGitHooks()

    result = set_up_checkout(toolchain, environment, hooks, checkout)

    assert result == Ok(checkout)
    assert checkout in toolchain.installed
    assert checkout in environment.synced
    assert checkout in hooks.hooked


def test_failure_is_returned() -> None:
    failure = ToolFailedError.fake()

    result = set_up_checkout(
        FakeToolchain(),
        FakePythonEnvironment(failure),
        FakeGitHooks(),
        CheckoutPath.fake(),
    )

    assert result == Err(failure)
