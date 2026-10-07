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


class RepositoryPath(RootModel[str]):
    """A file's path relative to the repository root, with `/` separators."""

    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return self.root

    @staticmethod
    def fake() -> RepositoryPath:
        return RepositoryPath("src/module.py")


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
        """Drop the change to the file at `path`, before or after the change."""
        return FileChanges(
            tuple(
                change
                for change in self.root
                if path
                not in {
                    version.path for version in (change.before, change.after) if version
                }
            )
        )


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
