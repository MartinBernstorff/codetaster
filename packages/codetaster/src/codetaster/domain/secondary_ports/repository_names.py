from typing import Protocol

from safe_result import Result

from codetaster.domain.domain_model.checkout import CheckoutPath, RepositoryName
from codetaster.domain.domain_model.tool_errors import ToolError


class RepositoryNames(Protocol):
    """Names repositories, through git."""

    def read_repository_name(
        self, checkout: CheckoutPath
    ) -> Result[RepositoryName, ToolError]:
        """The name of the directory holding the repository's main checkout.

        Every worktree of a repository has the same name, whatever its own
        directory is called.
        """
        ...
