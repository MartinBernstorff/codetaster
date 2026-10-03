from safe_result import Err, Ok

from codetaster_cli.domain.application_services.tear_down_checkout import (
    tear_down_checkout,
)
from codetaster_cli.domain.domain_model.checkout import CheckoutPath
from codetaster_cli.domain.domain_model.tool_errors import ToolFailedError
from codetaster_cli.domain.domain_model.worktrees import WorktreeCount
from codetaster_cli.infrastructure.fakes.call_log import CallLog, RecordedCall
from codetaster_cli.infrastructure.git_hooks.fake_git_hooks import FakeGitHooks
from codetaster_cli.infrastructure.git_worktrees.fake_git_worktrees import (
    FakeGitWorktrees,
)
from codetaster_cli.infrastructure.python_environment.fake_python_environment import (
    FakePythonEnvironment,
)
from codetaster_cli.infrastructure.task_cache.fake_task_cache import FakeTaskCache


def test_last_checkout_uninstalls_hooks_before_removing_the_virtualenv() -> None:
    log = CallLog.fake()

    result = tear_down_checkout(
        FakeGitWorktrees(log, WorktreeCount(1)),
        FakeGitHooks(log),
        FakePythonEnvironment(log),
        FakeTaskCache(log),
        CheckoutPath.fake(),
    )

    assert result == Ok(CheckoutPath.fake())
    assert log == CallLog(
        [
            RecordedCall.COUNT_WORKTREES,
            RecordedCall.UNINSTALL_HOOKS,
            RecordedCall.REMOVE_VIRTUALENV,
            RecordedCall.CLEAR_CACHE,
        ]
    )


def test_keeps_shared_hooks_while_other_worktrees_exist() -> None:
    log = CallLog.fake()

    result = tear_down_checkout(
        FakeGitWorktrees(log, WorktreeCount(2)),
        FakeGitHooks(log),
        FakePythonEnvironment(log),
        FakeTaskCache(log),
        CheckoutPath.fake(),
    )

    assert result == Ok(CheckoutPath.fake())
    assert log == CallLog(
        [
            RecordedCall.COUNT_WORKTREES,
            RecordedCall.REMOVE_VIRTUALENV,
            RecordedCall.CLEAR_CACHE,
        ]
    )


def test_stops_when_worktrees_cannot_be_counted() -> None:
    log = CallLog.fake()
    failure = ToolFailedError.fake()

    result = tear_down_checkout(
        FakeGitWorktrees(log, WorktreeCount.fake(), failure),
        FakeGitHooks(log),
        FakePythonEnvironment(log),
        FakeTaskCache(log),
        CheckoutPath.fake(),
    )

    assert result == Err(failure)
    assert log == CallLog([RecordedCall.COUNT_WORKTREES])
