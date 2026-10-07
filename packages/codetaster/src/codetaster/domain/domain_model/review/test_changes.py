import pytest
from pydantic import ValidationError

from codetaster.domain.domain_model.review.changes import (
    BlobSha,
    ChangeType,
    FileChange,
    FileChanges,
    FileVersion,
    RepositoryPath,
)


def added(path: RepositoryPath) -> FileChange:
    return FileChange(
        before=None, after=FileVersion.fake().model_copy(update={"path": path})
    )


def test_without_drops_the_change_to_a_path() -> None:
    dropped = RepositoryPath("dropped.py")
    kept = added(RepositoryPath("kept.py"))

    assert FileChanges((added(dropped), kept)).without(dropped) == FileChanges((kept,))


def test_without_keeps_a_file_renamed_away_from_the_path() -> None:
    path = RepositoryPath("dropped.py")
    before = FileVersion.fake().model_copy(update={"path": path})
    renamed = FileChanges((FileChange(before=before, after=FileVersion.fake()),))

    assert renamed.without(path) == renamed


def test_without_drops_a_file_renamed_to_the_path() -> None:
    dropped = RepositoryPath("dropped.py")
    after = FileVersion.fake().model_copy(update={"path": dropped})
    renamed = FileChange(before=FileVersion.fake(), after=after)

    assert FileChanges((renamed,)).without(dropped) == FileChanges(())


def test_without_drops_a_deleted_file_at_the_path() -> None:
    dropped = RepositoryPath("dropped.py")
    before = FileVersion.fake().model_copy(update={"path": dropped})
    deleted = FileChange(before=before, after=None)

    assert FileChanges((deleted,)).without(dropped) == FileChanges(())


@pytest.mark.parametrize(
    "spelling", ["./.codetaster/ratings.json", ".codetaster//ratings.json"]
)
def test_without_matches_another_spelling_of_the_path(spelling: str) -> None:
    changes = FileChanges((added(RepositoryPath(".codetaster/ratings.json")),))

    assert changes.without(RepositoryPath(spelling)) == FileChanges(())


def test_a_file_only_after_is_added() -> None:
    after = FileVersion.fake()

    change = FileChange(before=None, after=after)

    assert change.change_type() is ChangeType.ADDED
    assert change.path() == after.path


def test_a_file_only_before_is_deleted_and_keeps_its_old_path() -> None:
    before = FileVersion.fake()

    change = FileChange(before=before, after=None)

    assert change.change_type() is ChangeType.DELETED
    assert change.path() == before.path


def test_a_file_at_the_same_path_is_modified() -> None:
    before = FileVersion.fake()
    after = before.model_copy(update={"blob": BlobSha("b" * 40)})

    change = FileChange(before=before, after=after)

    assert change.change_type() is ChangeType.MODIFIED


def test_a_file_at_a_new_path_is_renamed_and_uses_the_new_path() -> None:
    before = FileVersion.fake()
    new_path = RepositoryPath("new/name.py")
    after = before.model_copy(update={"path": new_path})

    change = FileChange(before=before, after=after)

    assert change.change_type() is ChangeType.RENAMED
    assert change.path() == new_path


def test_a_change_needs_a_before_or_an_after() -> None:
    with pytest.raises(ValidationError):
        _ = FileChange(before=None, after=None)
