from pathlib import Path
from typing import override

from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.checkout import CheckoutPath, RepositoryName
from codetaster.domain.domain_model.tool_errors import ToolError
from codetaster.domain.secondary_ports.repository_names import RepositoryNames
from codetaster.infrastructure.committed_changes.git_committed_changes import (
    GitArguments,
    run_git,
)


class GitRepositoryNames(RepositoryNames):
    @override
    def read_repository_name(
        self, checkout: CheckoutPath
    ) -> Result[RepositoryName, ToolError]:
        # The common directory is shared by every worktree: `<main checkout>/.git`,
        # or the repository itself if it is bare.
        common_directory = run_git(
            checkout,
            GitArguments(("rev-parse", "--path-format=absolute", "--git-common-dir")),
        )
        if isinstance(common_directory, Err):
            return common_directory
        return Ok(
            repository_name_from_common_directory(
                CheckoutPath(Path(common_directory.value.root.strip()))
            )
        )


def repository_name_from_common_directory(directory: CheckoutPath) -> RepositoryName:
    """`project` for `project/.git` and `project/.bare`; `project` for `project.git`."""
    name = directory.root.name
    if name.startswith("."):
        return RepositoryName(directory.root.parent.name)
    return RepositoryName(name.removesuffix(".git"))
