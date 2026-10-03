from typing import override

from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.tool_errors import ToolError
from codetaster.domain.secondary_ports.python_environment import (
    PythonEnvironment,
)
from codetaster.infrastructure.fakes.call_log import CallLog, RecordedCall


class FakePythonEnvironment(PythonEnvironment):
    def __init__(self, log: CallLog, failure: ToolError | None = None) -> None:
        self.log = log
        self.failure = failure

    @override
    def sync_dependencies(self, checkout: CheckoutPath) -> Result[None, ToolError]:
        self.log.record(RecordedCall.SYNC_DEPENDENCIES)
        return Ok(None) if self.failure is None else Err(self.failure)
