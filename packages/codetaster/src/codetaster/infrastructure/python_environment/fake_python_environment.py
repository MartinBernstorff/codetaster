from typing import override

from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.tool_errors import ToolError
from codetaster.domain.secondary_ports.python_environment import PythonEnvironment


class FakePythonEnvironment(PythonEnvironment):
    """Keeps the checkouts it synced in `synced`, so tests can inspect them."""

    def __init__(self, failure: ToolError | None = None) -> None:
        self.synced: set[CheckoutPath] = set()
        self.failure = failure

    @override
    def sync_dependencies(self, checkout: CheckoutPath) -> Result[None, ToolError]:
        if self.failure is not None:
            return Err(self.failure)
        self.synced.add(checkout)
        return Ok(None)
