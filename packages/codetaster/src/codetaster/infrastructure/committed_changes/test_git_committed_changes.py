"""What only git does: detect renames of edited files, and diff any path."""

from pathlib import Path

from codetaster.domain.domain_model.review.changes import (
    ChangeLineHunks,
    RepositoryPath,
)
from codetaster.infrastructure.committed_changes.test_contract import (
    FileText,
    GitRepository,
    HunkHeader,
    change_from_main,
    hunk,
    line_hunks_of,
)


def test_an_edited_rename_has_its_hunks_under_its_new_path(tmp_path: Path) -> None:
    repository = GitRepository(tmp_path.resolve())
    old = RepositoryPath("old.py")
    new = RepositoryPath("new.py")
    expected = (hunk(HunkHeader("-5,1 +5,1")),)
    change = change_from_main(
        repository,
        edits={old: None, new: FileText("1\n2\n3\n4\nfive\n")},
        base_edits={old: FileText("1\n2\n3\n4\n5\n")},
    )

    hunks = line_hunks_of(repository, change)

    assert hunks == ChangeLineHunks({new: expected})


def test_paths_git_would_quote_get_their_hunks(tmp_path: Path) -> None:
    repository = GitRepository(tmp_path.resolve())
    spaced = RepositoryPath("with space.py")
    accented = RepositoryPath("ünïcode.py")
    expected = (hunk(HunkHeader("-0,0 +1,1")),)
    change = change_from_main(
        repository,
        edits={spaced: FileText("a\n"), accented: FileText("b\n")},
    )

    hunks = line_hunks_of(repository, change)

    assert hunks == ChangeLineHunks({spaced: expected, accented: expected})
