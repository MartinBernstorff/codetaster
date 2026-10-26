import difflib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import override

from pydantic import ConfigDict, RootModel
from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.review.changes import (
    BlobContent,
    BlobLineCounts,
    BlobSha,
    ChangeLineHunks,
    CommitSha,
    CommittedChange,
    FileChange,
    FileChanges,
    FileVersion,
    HunkStart,
    LineCount,
    LineHunk,
    LineSpan,
    RepositoryPath,
    RevisionName,
    WorkingTreeState,
)
from codetaster.domain.domain_model.review.errors import UnknownRevisionError
from codetaster.domain.domain_model.tool_errors import ToolError
from codetaster.domain.secondary_ports.committed_changes import (
    ChangeReadError,
    CommittedChanges,
)

type Tree = Mapping[RepositoryPath, BlobSha]


class FileLines(RootModel[tuple[bytes, ...]]):
    """A file's lines, each with its line break."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> FileLines:
        return FileLines((b"content\n",))


@dataclass(frozen=True)
class FakeCommit:
    parent: CommitSha | None
    tree: Tree


class FakeCommittedChanges(CommittedChanges):
    """A linear history per branch, built with `commit`, `create_branch` and `switch_to`.

    Ignores the checkout: every directory is in the one at `repository_root`.
    Detects renames only when the content is unchanged. Knows the line count of the
    blobs in `line_counts`, and diffs the blobs in `contents`, finding the changed
    lines with difflib rather than git's algorithm. A blob it has no content for, or
    whose content git would deem binary, has no changed lines.
    """

    def __init__(self, initial_branch: RevisionName) -> None:
        self.commits: dict[CommitSha, FakeCommit] = {}
        self.branches: dict[RevisionName, CommitSha] = {}
        self.current_branch = initial_branch
        self.working_tree = WorkingTreeState.CLEAN
        self.repository_root = CheckoutPath.fake()
        self.line_counts: dict[BlobSha, LineCount] = {}
        self.contents: dict[BlobSha, BlobContent] = {}

    def commit(self, edits: Mapping[RepositoryPath, BlobSha | None]) -> CommitSha:
        """Commit on the current branch. A `None` blob deletes the file."""
        parent = self.branches.get(self.current_branch)
        tree: dict[RepositoryPath, BlobSha] = (
            dict(self.commits[parent].tree) if parent is not None else {}
        )
        for path, blob in edits.items():
            if blob is None:
                del tree[path]
            else:
                tree[path] = blob
        sha = CommitSha(f"{len(self.commits) + 1:040x}")
        self.commits[sha] = FakeCommit(parent=parent, tree=tree)
        self.branches[self.current_branch] = sha
        return sha

    def create_branch(self, name: RevisionName) -> None:
        """Create `name` at the current commit and switch to it."""
        self.branches[name] = self.branches[self.current_branch]
        self.current_branch = name

    def switch_to(self, name: RevisionName) -> None:
        self.current_branch = name

    @override
    def read_committed_change(
        self, checkout: CheckoutPath, base: RevisionName
    ) -> Result[CommittedChange, ChangeReadError]:
        base_commit = self.branches.get(base)
        if base_commit is None:
            return Err(UnknownRevisionError(base))
        head = self.branches[self.current_branch]
        base_ancestors = set(self.ancestry(base_commit))
        merge_base = next(
            commit for commit in self.ancestry(head) if commit in base_ancestors
        )
        return Ok(
            CommittedChange(
                base=base,
                merge_base=merge_base,
                head=head,
                files=diff_trees(
                    self.commits[merge_base].tree, self.commits[head].tree
                ),
            )
        )

    @override
    def read_working_tree_state(
        self, checkout: CheckoutPath
    ) -> Result[WorkingTreeState, ToolError]:
        return Ok(self.working_tree)

    @override
    def read_repository_root(
        self, checkout: CheckoutPath
    ) -> Result[CheckoutPath, ToolError]:
        return Ok(self.repository_root)

    @override
    def read_line_counts(
        self, checkout: CheckoutPath, blobs: tuple[BlobSha, ...]
    ) -> Result[BlobLineCounts, ToolError]:
        return Ok(
            BlobLineCounts(
                {
                    blob: self.line_counts[blob]
                    for blob in blobs
                    if blob in self.line_counts
                }
            )
        )

    @override
    def read_line_hunks(
        self, checkout: CheckoutPath, change: CommittedChange
    ) -> Result[ChangeLineHunks, ToolError]:
        hunks = {file.path(): self.diff_lines(file) for file in change.files.root}
        return Ok(
            ChangeLineHunks({path: found for path, found in hunks.items() if found})
        )

    def diff_lines(self, change: FileChange) -> tuple[LineHunk, ...]:
        before = self.lines_of(None if change.before is None else change.before.blob)
        after = self.lines_of(None if change.after is None else change.after.blob)
        if before is None or after is None:
            return ()
        opcodes = difflib.SequenceMatcher(
            None, before.root, after.root, autojunk=False
        ).get_opcodes()
        # As in a diff's hunk header, an empty span starts at the line before it.
        return tuple(
            LineHunk(
                before=LineSpan(
                    start=HunkStart(before_start + (before_end > before_start)),
                    count=LineCount(before_end - before_start),
                ),
                after=LineSpan(
                    start=HunkStart(after_start + (after_end > after_start)),
                    count=LineCount(after_end - after_start),
                ),
            )
            for tag, before_start, before_end, after_start, after_end in opcodes
            if tag != "equal"
        )

    def lines_of(self, blob: BlobSha | None) -> FileLines | None:
        """Each line with its line break. Empty for a missing side, `None` if the
        content is unknown or binary, as git deems a NUL in the first 8000 bytes."""
        if blob is None:
            return FileLines(())
        content = self.contents.get(blob)
        if content is None or b"\0" in content.root[:8000]:
            return None
        return FileLines(tuple(re.findall(rb"[^\n]*\n|[^\n]+$", content.root)))

    def ancestry(self, commit: CommitSha) -> list[CommitSha]:
        """`commit`, then its parent, and so on to the root."""
        chain: list[CommitSha] = []
        current: CommitSha | None = commit
        while current is not None:
            chain.append(current)
            current = self.commits[current].parent
        return chain


def diff_trees(before: Tree, after: Tree) -> FileChanges:
    removed = {path: blob for path, blob in before.items() if path not in after}
    changes: list[FileChange] = []
    for path, blob in after.items():
        if before.get(path) == blob:
            continue
        if path in before:
            previous = FileVersion(path=path, blob=before[path])
        else:
            renamed_from = next(
                (old for old, old_blob in removed.items() if old_blob == blob), None
            )
            previous = None
            if renamed_from is not None:
                previous = FileVersion(
                    path=renamed_from, blob=removed.pop(renamed_from)
                )
        changes.append(
            FileChange(before=previous, after=FileVersion(path=path, blob=blob))
        )
    changes.extend(
        FileChange(before=FileVersion(path=path, blob=blob), after=None)
        for path, blob in removed.items()
    )
    return FileChanges(tuple(sorted(changes, key=lambda change: change.path().root)))
