import pytest
from pydantic import ValidationError

from codetaster.domain.domain_model.review.changes import (
    BlobSha,
    ChangeType,
    FileChange,
    FileVersion,
    RepositoryPath,
)


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
