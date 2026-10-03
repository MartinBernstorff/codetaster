from typing import override

from safe_result import Err, Ok, Result

from codetaster_cli.domain.domain_model.checkout import CheckoutPath
from codetaster_cli.domain.domain_model.tool_errors import ToolError
from codetaster_cli.domain.secondary_ports.git_hooks import GitHooks
from codetaster_cli.infrastructure.fakes.call_log import CallLog, RecordedCall


class FakeGitHooks(GitHooks):
    def __init__(self, log: CallLog, failure: ToolError | None = None) -> None:
        self.log = log
        self.failure = failure

    @override
    def install_hooks(self, checkout: CheckoutPath) -> Result[None, ToolError]:
        self.log.record(RecordedCall.INSTALL_HOOKS)
        return Ok(None) if self.failure is None else Err(self.failure)

    @override
    def uninstall_hooks(self, checkout: CheckoutPath) -> Result[None, ToolError]:
        self.log.record(RecordedCall.UNINSTALL_HOOKS)
        return Ok(None) if self.failure is None else Err(self.failure)
