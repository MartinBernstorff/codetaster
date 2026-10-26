import re
from pathlib import Path
from typing import override

from pydantic import BaseModel, ConfigDict, RootModel
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
    BinaryToolOutput,
    OutputMode,
    ToolArguments,
    ToolInput,
    ToolOutput,
    run_external_tool,
    run_external_tool_on_input,
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
        # paths unquoted. -r and -z have no long form.
        diff = run_git(
            checkout,
            GitArguments(
                (
                    "diff-tree",
                    "-r",
                    "-z",
                    "--find-renames",
                    merge_base_commit.root,
                    head.value.root,
                )
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
        status = run_git(checkout, GitArguments(("status", "--porcelain", "--null")))
        if isinstance(status, Err):
            return status
        if status.value.root == "":
            return Ok(WorkingTreeState.CLEAN)
        return Ok(WorkingTreeState.DIRTY)

    @override
    def read_repository_root(
        self, checkout: CheckoutPath
    ) -> Result[CheckoutPath, ToolError]:
        root = run_git(checkout, GitArguments(("rev-parse", "--show-toplevel")))
        if isinstance(root, Err):
            return root
        return Ok(CheckoutPath(Path(root.value.root.strip())))

    @override
    def read_line_counts(
        self, checkout: CheckoutPath, blobs: tuple[BlobSha, ...]
    ) -> Result[BlobLineCounts, ToolError]:
        if not blobs:
            return Ok(BlobLineCounts({}))
        # Bytes, not text: content need not be UTF-8, and a lone \r is no line break.
        output = run_external_tool_on_input(
            ToolArguments(("git", "cat-file", "--batch")),
            checkout,
            ToolInput("".join(f"{blob.root}\n" for blob in blobs).encode()),
            git_installation_hint(),
        )
        if isinstance(output, Err):
            return output
        return Ok(parse_batch_line_counts(output.value))

    @override
    def read_line_hunks(
        self, checkout: CheckoutPath, change: CommittedChange
    ) -> Result[ChangeLineHunks, ToolError]:
        # The raw records name each file, unquoted with -z, and come in the same
        # order as the patches. Bytes, as file content need not be UTF-8.
        output = run_external_tool_on_input(
            ToolArguments(
                (
                    "git",
                    "diff-tree",
                    "-r",
                    "-z",
                    "--find-renames",
                    "--raw",
                    "--patch",
                    "--unified=0",
                    "--no-ext-diff",
                    "--no-textconv",
                    change.merge_base.root,
                    change.head.root,
                )
            ),
            checkout,
            ToolInput(b""),
            git_installation_hint(),
        )
        if isinstance(output, Err):
            return output
        return Ok(parse_raw_diff_with_patches(output.value))


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


def git_installation_hint() -> InstallationHint:
    return InstallationHint("Install git from https://git-scm.com/downloads.")


def run_git(
    checkout: CheckoutPath, arguments: GitArguments
) -> Result[ToolOutput, ToolError]:
    return run_external_tool(
        ToolArguments(("git", *arguments.root)),
        checkout,
        OutputMode.CAPTURE,
        git_installation_hint(),
    )


class RawDiffFields(RootModel[tuple[bytes, ...]]):
    """The NUL-separated fields of `git diff-tree -z` output."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> RawDiffFields:
        return RawDiffFields(())


class RawRecords(BaseModel):
    """The changes in the raw records at the start of some fields, in git's order,
    and the fields after them."""

    model_config = ConfigDict(frozen=True)

    changes: tuple[FileChange, ...]
    rest: RawDiffFields

    @staticmethod
    def fake() -> RawRecords:
        return RawRecords(changes=(), rest=RawDiffFields.fake())


def parse_raw_diff(output: ToolOutput) -> FileChanges:
    """Parse `git diff-tree -r -z` output, ordering the changes by path."""
    records = parse_raw_records(RawDiffFields(tuple(output.root.encode().split(b"\0"))))
    return FileChanges(
        tuple(sorted(records.changes, key=lambda change: change.path().root))
    )


def parse_raw_records(fields: RawDiffFields) -> RawRecords:
    """Parse the raw records at the start of `fields`.

    Each record is `:<old mode> <new mode> <old blob> <new blob> <status>`, then
    the path, then for a rename (status `R<score>`) the new path.
    """
    texts = tuple(field.decode() for field in fields.root)
    changes: list[FileChange] = []
    index = 0
    while index < len(texts) and texts[index].startswith(":"):
        _, _, old_blob, new_blob, status = texts[index].removeprefix(":").split(" ")
        old_path = RepositoryPath(texts[index + 1])
        new_path = old_path
        index += 2
        if status.startswith("R"):
            new_path = RepositoryPath(texts[index])
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
    return RawRecords(changes=tuple(changes), rest=RawDiffFields(fields.root[index:]))


def parse_raw_diff_with_patches(output: BinaryToolOutput) -> ChangeLineHunks:
    """Parse `git diff-tree -r -z --raw --patch --unified=0` output.

    The raw records come first, then an empty field, then one patch per record, in
    the same order, each starting with a `diff --git` line. Its other lines are
    headers, or content lines that start with ` `, `-`, `+` or `\\`, so only real
    headers start with `diff --git` or `@@`.
    """
    records = parse_raw_records(RawDiffFields(tuple(output.root.split(b"\0"))))
    patch_lines = b"\0".join(records.rest.root[1:]).split(b"\n")
    hunks_per_file: list[list[LineHunk]] = []
    for line in patch_lines:
        if line.startswith(b"diff --git "):
            hunks_per_file.append([])
            continue
        header = HUNK_HEADER.match(line)
        if header is None or not hunks_per_file:
            continue
        # A missing count means 1 line.
        before_start, before_count, after_start, after_count = header.groups()
        hunks_per_file[-1].append(
            LineHunk(
                before=LineSpan(
                    start=HunkStart(int(before_start)),
                    count=LineCount(1 if before_count is None else int(before_count)),
                ),
                after=LineSpan(
                    start=HunkStart(int(after_start)),
                    count=LineCount(1 if after_count is None else int(after_count)),
                ),
            )
        )
    return ChangeLineHunks(
        {
            change.path(): tuple(hunks)
            for change, hunks in zip(records.changes, hunks_per_file, strict=True)
            if hunks
        }
    )


HUNK_HEADER = re.compile(rb"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def parse_batch_line_counts(output: BinaryToolOutput) -> BlobLineCounts:
    """Count the lines of each blob in `git cat-file --batch` output.

    Each object is `<sha> <type> <size>\\n`, then `size` bytes of content and a
    `\\n`. An object git cannot find is `<sha> missing\\n` (or `ambiguous`).
    """
    data = output.root
    counts: dict[BlobSha, LineCount] = {}
    position = 0
    while position < len(data):
        header_end = data.index(b"\n", position)
        header = data[position:header_end].decode().split(" ")
        position = header_end + 1
        match header:
            case [sha, object_type, size]:
                content = data[position : position + int(size)]
                position += int(size) + 1
                if object_type == "blob":
                    counts[BlobSha(sha)] = LineCount.of_content(BlobContent(content))
            case _:
                pass
    return BlobLineCounts(counts)
