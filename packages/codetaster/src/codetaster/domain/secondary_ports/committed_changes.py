from typing import Protocol

from safe_result import Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.review.changes import (
    BlobLineCounts,
    BlobSha,
    CommittedChange,
    RevisionName,
    WorkingTreeState,
)
from codetaster.domain.domain_model.review.errors import UnknownRevisionError
from codetaster.domain.domain_model.tool_errors import ToolError

type ChangeReadError = UnknownRevisionError | ToolError


class CommittedChanges(Protocol):
    """The commits in a checkout, read through git."""

    def read_committed_change(
        self, checkout: CheckoutPath, base: RevisionName
    ) -> Result[CommittedChange, ChangeReadError]:
        """The files changed from the merge base of `base` and HEAD, to HEAD.

        Renames are detected, so a moved file is one change rather than a
        deletion and an addition.
        """
        ...

    def read_working_tree_state(
        self, checkout: CheckoutPath
    ) -> Result[WorkingTreeState, ToolError]:
        """Dirty if anything is uncommitted, including untracked files."""
        ...

    def read_repository_root(
        self, checkout: CheckoutPath
    ) -> Result[CheckoutPath, ToolError]:
        """The top directory of the checkout `checkout` is in, which may be itself."""
        ...

    def read_line_counts(
        self, checkout: CheckoutPath, blobs: tuple[BlobSha, ...]
    ) -> Result[BlobLineCounts, ToolError]:
        """How many lines each of the files with content `blobs` has, read at once.

        A blob that does not exist, or names something other than a file's
        content (such as a submodule's commit), is left out.
        """
        ...
