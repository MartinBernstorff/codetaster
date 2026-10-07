from collections.abc import Mapping
from typing import override

from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.checkout import CheckoutPath, RepositoryName
from codetaster.domain.domain_model.tool_errors import (
    ExitCode,
    ToolError,
    ToolFailedError,
    ToolInvocation,
)
from codetaster.domain.secondary_ports.repository_names import RepositoryNames


class FakeRepositoryNames(RepositoryNames):
    """Names the checkouts in `names`. Any other directory is not in a repository."""

    def __init__(self, names: Mapping[CheckoutPath, RepositoryName]) -> None:
        self.names = dict(names)

    @override
    def read_repository_name(
        self, checkout: CheckoutPath
    ) -> Result[RepositoryName, ToolError]:
        name = self.names.get(checkout)
        if name is None:
            return Err(
                ToolFailedError(
                    ToolInvocation("git rev-parse --git-common-dir"), ExitCode(128)
                )
            )
        return Ok(name)
