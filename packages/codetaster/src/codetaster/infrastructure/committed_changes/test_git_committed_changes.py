"""What only git does: detect renames of edited files and type changes, and diff
any path and content."""

from pathlib import Path

from safe_result import Err, Ok

from codetaster.domain.domain_model.review.changes import (
    ChangeLineHunks,
    CommittedChange,
    RepositoryPath,
    RevisionName,
)
from codetaster.infrastructure.committed_changes.test_contract import (
    FileText,
    GitRepository,
    HunkHeader,
    change_from_main,
    line_hunk_from_header,
    line_hunks_of,
)


def test_an_edited_rename_has_its_hunks_under_its_new_path(tmp_path: Path) -> None:
    repository = GitRepository(tmp_path.resolve())
    old = RepositoryPath("old.py")
    new = RepositoryPath("new.py")
    expected = (line_hunk_from_header(HunkHeader("-5,1 +5,1")),)
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
    expected = (line_hunk_from_header(HunkHeader("-0,0 +1,1")),)
    change = change_from_main(
        repository,
        edits={spaced: FileText("a\n"), accented: FileText("b\n")},
    )

    hunks = line_hunks_of(repository, change)

    assert hunks == ChangeLineHunks({spaced: expected, accented: expected})


def test_a_file_turned_into_a_symlink_has_the_hunks_of_both_versions(
    tmp_path: Path,
) -> None:
    repository = GitRepository(tmp_path.resolve())
    path = RepositoryPath("link")
    # git diffs a type change as a deletion of the file and an addition of the link.
    expected = (
        line_hunk_from_header(HunkHeader("-1,2 +0,0")),
        line_hunk_from_header(HunkHeader("-0,0 +1,1")),
    )
    _ = repository.commit({path: FileText("one\ntwo\n")})
    repository.create_branch(RevisionName("feature"))
    (tmp_path.resolve() / path.root).unlink()
    (tmp_path.resolve() / path.root).symlink_to("target")
    _ = repository.commit({})
    change = read_change(repository)

    hunks = line_hunks_of(repository, change)

    assert hunks == ChangeLineHunks({path: expected})


def test_a_file_that_is_not_utf8_gets_its_hunks(tmp_path: Path) -> None:
    repository = GitRepository(tmp_path.resolve())
    path = RepositoryPath("latin1.txt")
    expected = (line_hunk_from_header(HunkHeader("-0,0 +1,1")),)
    _ = repository.commit({RepositoryPath("README.md"): FileText.fake()})
    repository.create_branch(RevisionName("feature"))
    _ = (tmp_path.resolve() / path.root).write_bytes("café\n".encode("latin-1"))
    _ = repository.commit({})
    change = read_change(repository)

    hunks = line_hunks_of(repository, change)

    assert hunks == ChangeLineHunks({path: expected})


def read_change(repository: GitRepository) -> CommittedChange:
    match repository.changes.read_committed_change(
        repository.checkout, repository.initial_branch
    ):
        case Ok(change):
            return change
        case Err(error):
            raise error
