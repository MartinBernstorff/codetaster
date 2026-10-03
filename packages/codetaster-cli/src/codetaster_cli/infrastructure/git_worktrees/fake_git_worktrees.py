from typing import override

from safe_result import Err, Ok, Result

from codetaster_cli.domain.domain_model.checkout import CheckoutPath
from codetaster_cli.domain.domain_model.tool_errors import ToolError
from codetaster_cli.domain.domain_model.worktrees import WorktreeCount
from codetaster_cli.domain.secondary_ports.git_worktrees import GitWorktrees
from codetaster_cli.infrastructure.fakes.call_log import CallLog, RecordedCall


class FakeGitWorktrees(GitWorktrees):
    def __init__(
        self, log: CallLog, count: WorktreeCount, failure: ToolError | None = None
    ) -> None:
        self.log = log
        self.count = count
        self.failure = failure

    @override
    def count_worktrees(
        self, checkout: CheckoutPath
    ) -> Result[WorktreeCount, ToolError]:
        self.log.record(RecordedCall.COUNT_WORKTREES)
        return Ok(self.count) if self.failure is None else Err(self.failure)
