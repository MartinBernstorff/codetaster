import shutil
from typing import override

from safe_result import Ok, Result

from codetaster_cli.domain.domain_model.checkout import CheckoutPath
from codetaster_cli.domain.domain_model.tool_errors import ToolError
from codetaster_cli.domain.secondary_ports.task_cache import TaskCache


class MoonTaskCache(TaskCache):
    """moon's cache directory, `.moon/cache`."""

    @override
    def clear_cache(self, checkout: CheckoutPath) -> Result[None, ToolError]:
        shutil.rmtree(checkout.root / ".moon" / "cache", ignore_errors=True)
        return Ok(None)
