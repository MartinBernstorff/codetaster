import posixpath
from enum import StrEnum
from typing import Annotated, Self, override

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator


class RevisionName(RootModel[Annotated[str, Field(min_length=1)]]):
    """Anything git resolves to a commit, such as `main` or `origin/main`."""

    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return self.root

    @staticmethod
    def fake() -> RevisionName:
        return RevisionName("main")


class CommitSha(RootModel[str]):
    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return self.root

    @staticmethod
    def fake() -> CommitSha:
        return CommitSha("1" * 40)


class BlobSha(RootModel[str]):
    """Git's id for a file's content."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> BlobSha:
        return BlobSha("a" * 40)


class BlobContent(RootModel[bytes]):
    """A file version's content, byte for byte."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> BlobContent:
        return BlobContent(b"content\n")


class LineCount(RootModel[Annotated[int, Field(ge=0)]]):
    """How many lines a file has, as a diff numbers them."""

    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return str(self.root)

    @staticmethod
    def fake() -> LineCount:
        return LineCount(1)

    @staticmethod
    def of_content(content: BlobContent) -> LineCount:
        """Counted as git does: each line ends at a `\\n`, and a last line without
        one counts too. A lone `\\r` is not a line break; an empty file has no lines.
        """
        data = content.root
        unterminated = 1 if data and not data.endswith(b"\n") else 0
        return LineCount(data.count(b"\n") + unterminated)


class BlobLineCounts(RootModel[dict[BlobSha, LineCount]]):
    """How many lines each file version has, by its blob."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> BlobLineCounts:
        return BlobLineCounts({BlobSha.fake(): LineCount.fake()})


class HunkStart(RootModel[Annotated[int, Field(ge=0)]]):
    """Where a hunk's lines start in one version of a file, as a diff numbers them.

    Counting from 1. A hunk with no lines in that version starts at the line
    before the gap, which is 0 at the top of the file.
    """

    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return str(self.root)

    @staticmethod
    def fake() -> HunkStart:
        return HunkStart(1)


class LineSpan(BaseModel):
    """The lines a hunk covers in one version of a file, as in a diff's
    `@@ -start,count +start,count @@` header."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    start: HunkStart = Field(
        description="The first line, counting from 1. With a count of 0, the line "
        "before the gap, or 0 at the top of the file."
    )
    count: LineCount = Field(description="How many lines. 0 if there are none.")

    @staticmethod
    def fake() -> LineSpan:
        return LineSpan(start=HunkStart.fake(), count=LineCount.fake())


class LineHunk(BaseModel):
    """A run of changed lines, as `git diff --unified=0` reports it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    before: LineSpan = Field(description="The lines in the before version.")
    after: LineSpan = Field(description="The lines in the after version.")

    @staticmethod
    def fake() -> LineHunk:
        return LineHunk(before=LineSpan.fake(), after=LineSpan.fake())


class RepositoryPath(RootModel[str]):
    """A file's path relative to the repository root, with `/` separators."""

    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return self.root

    @staticmethod
    def fake() -> RepositoryPath:
        return RepositoryPath("src/module.py")

    def normalised(self) -> RepositoryPath:
        """Without `./`, `..` or repeated `/`, as git writes paths."""
        return RepositoryPath(posixpath.normpath(self.root))


class FileVersion(BaseModel):
    """A file as it is in one commit."""

    model_config = ConfigDict(frozen=True)

    path: RepositoryPath
    blob: BlobSha

    @staticmethod
    def fake() -> FileVersion:
        return FileVersion(path=RepositoryPath.fake(), blob=BlobSha.fake())


class ChangeType(StrEnum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


class FileChange(BaseModel):
    """One file's change. `before` is `None` if it was added, `after` if deleted."""

    model_config = ConfigDict(frozen=True)

    before: FileVersion | None
    after: FileVersion | None

    @model_validator(mode="after")
    def has_a_version(self) -> Self:
        if self.before is None and self.after is None:
            msg = "a file change needs a before or an after version"
            raise ValueError(msg)
        return self

    @staticmethod
    def fake() -> FileChange:
        return FileChange(before=None, after=FileVersion.fake())

    def change_type(self) -> ChangeType:
        if self.before is None:
            return ChangeType.ADDED
        if self.after is None:
            return ChangeType.DELETED
        if self.before.path == self.after.path:
            return ChangeType.MODIFIED
        return ChangeType.RENAMED

    def path(self) -> RepositoryPath:
        """The new path, or the old one if the file was deleted."""
        version = self.after or self.before
        assert version is not None
        return version.path

    def previous_path(self) -> RepositoryPath | None:
        """The old path if the file was renamed."""
        if self.change_type() is not ChangeType.RENAMED:
            return None
        assert self.before is not None
        return self.before.path


class FileChanges(RootModel[tuple[FileChange, ...]]):
    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> FileChanges:
        return FileChanges((FileChange.fake(),))

    def without(self, path: RepositoryPath) -> FileChanges:
        """Drop the change whose file is at `path` after it, or was if it was deleted.

        A file renamed away from `path` is kept.
        """
        dropped = path.normalised()
        return FileChanges(
            tuple(
                change for change in self.root if change.path().normalised() != dropped
            )
        )


class ChangeLineHunks(RootModel[dict[RepositoryPath, tuple[LineHunk, ...]]]):
    """The changed lines of each file in a change, by the file's path.

    A file whose change has no lines, e.g. a binary file or a pure rename, has no
    hunks.
    """

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> ChangeLineHunks:
        return ChangeLineHunks({RepositoryPath.fake(): (LineHunk.fake(),)})

    def hunks_of(self, change: FileChange) -> tuple[LineHunk, ...]:
        return self.root.get(change.path(), ())

    def hunks_to_rate(self, change: FileChange) -> tuple[LineHunk | None, ...]:
        """The hunks a rating of `change` rates: its hunks, or one `None` for the
        whole change if it has no changed lines."""
        return self.hunks_of(change) or (None,)


class CommittedChange(BaseModel):
    """The files changed from the merge base of `base` and HEAD, to HEAD."""

    model_config = ConfigDict(frozen=True)

    base: RevisionName
    merge_base: CommitSha
    head: CommitSha
    files: FileChanges

    @staticmethod
    def fake() -> CommittedChange:
        return CommittedChange(
            base=RevisionName.fake(),
            merge_base=CommitSha.fake(),
            head=CommitSha.fake(),
            files=FileChanges.fake(),
        )


class WorkingTreeState(StrEnum):
    CLEAN = "clean"
    DIRTY = "dirty"
