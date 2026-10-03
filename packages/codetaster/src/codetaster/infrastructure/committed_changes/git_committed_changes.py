from typing import override

from pydantic import ConfigDict, RootModel
from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.review.changes import (
    BlobSha,
    CommitSha,
    CommittedChange,
    FileChange,
    FileChanges,
    FileVersion,
    RepositoryPath,
    RevisionName,
    WorkingTreeState,
)
from codetaster.domain.domain_model.review.errors import UnknownRevisionError
from codetaster.domain.domain_model.tool_errors import (
    InstallationHint,
    ToolError,
    ToolFailedError,
)
from codetaster.domain.secondary_ports.committed_changes import (
    ChangeReadError,
    CommittedChanges,
)
from codetaster.infrastructure.external_tool.run_external_tool import (
    OutputMode,
    ToolArguments,
    ToolOutput,
    run_external_tool,
)


class GitCommittedChanges(CommittedChanges):
    @override
    def read_committed_change(
        self, checkout: CheckoutPath, base: RevisionName
    ) -> Result[CommittedChange, ChangeReadError]:
        base_commit = resolve_commit(checkout, base)
        if isinstance(base_commit, Err):
            return base_commit
        head = resolve_commit(checkout, RevisionName("HEAD"))
        if isinstance(head, Err):
            return head
        merge_base = run_git(
            checkout,
            GitArguments(("merge-base", base_commit.value.root, head.value.root)),
        )
        if isinstance(merge_base, Err):
            return merge_base
        merge_base_commit = CommitSha(merge_base.value.root.strip())
        # Plumbing, so user diff config does not change the output. -z leaves
        # paths unquoted; -M detects renames.
        diff = run_git(
            checkout,
            GitArguments(
                ("diff-tree", "-r", "-z", "-M", merge_base_commit.root, head.value.root)
            ),
        )
        if isinstance(diff, Err):
            return diff
        return Ok(
            CommittedChange(
                base=base,
                merge_base=merge_base_commit,
                head=head.value,
                files=parse_raw_diff(diff.value),
            )
        )

    @override
    def read_working_tree_state(
        self, checkout: CheckoutPath
    ) -> Result[WorkingTreeState, ToolError]:
        status = run_git(checkout, GitArguments(("status", "--porcelain", "-z")))
        if isinstance(status, Err):
            return status
        if status.value.root == "":
            return Ok(WorkingTreeState.CLEAN)
        return Ok(WorkingTreeState.DIRTY)


def resolve_commit(
    checkout: CheckoutPath, revision: RevisionName
) -> Result[CommitSha, ChangeReadError]:
    resolved = run_git(
        checkout,
        GitArguments(
            (
                "rev-parse",
                "--verify",
                "--quiet",
                "--end-of-options",
                f"{revision.root}^{{commit}}",
            )
        ),
    )
    match resolved:
        case Ok(output):
            return Ok(CommitSha(output.root.strip()))
        # --verify --quiet exits 1, silently, for a revision that names nothing.
        case Err(ToolFailedError(exit_code=exit_code)) if exit_code.root == 1:
            return Err(UnknownRevisionError(revision))
        case Err(error):
            return Err(error)


class GitArguments(RootModel[tuple[str, ...]]):
    """A git subcommand and its arguments."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> GitArguments:
        return GitArguments(("status",))


def run_git(
    checkout: CheckoutPath, arguments: GitArguments
) -> Result[ToolOutput, ToolError]:
    return run_external_tool(
        ToolArguments(("git", *arguments.root)),
        checkout,
        OutputMode.CAPTURE,
        InstallationHint("Install git from https://git-scm.com/downloads."),
    )


def parse_raw_diff(output: ToolOutput) -> FileChanges:
    """Parse `git diff-tree -r -z` output.

    Each record is `:<old mode> <new mode> <old blob> <new blob> <status>`, then
    the path, then for a rename (status `R<score>`) the new path.
    """
    fields = output.root.split("\0")
    changes: list[FileChange] = []
    index = 0
    while index < len(fields) and fields[index].startswith(":"):
        _, _, old_blob, new_blob, status = fields[index].removeprefix(":").split(" ")
        old_path = RepositoryPath(fields[index + 1])
        new_path = old_path
        index += 2
        if status.startswith("R"):
            new_path = RepositoryPath(fields[index])
            index += 1
        changes.append(
            FileChange(
                before=None
                if status == "A"
                else FileVersion(path=old_path, blob=BlobSha(old_blob)),
                after=None
                if status == "D"
                else FileVersion(path=new_path, blob=BlobSha(new_blob)),
            )
        )
    return FileChanges(tuple(sorted(changes, key=lambda change: change.path().root)))
