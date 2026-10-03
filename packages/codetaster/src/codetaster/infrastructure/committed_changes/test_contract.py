"""Contract for CommittedChanges, run against every implementation."""

import hashlib
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, override

import pytest
from pydantic import RootModel
from safe_result import Err, Ok

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.review.changes import (
    BlobSha,
    ChangeType,
    CommitSha,
    CommittedChange,
    RepositoryPath,
    RevisionName,
    WorkingTreeState,
)
from codetaster.domain.domain_model.review.errors import UnknownRevisionError
from codetaster.domain.secondary_ports.committed_changes import CommittedChanges
from codetaster.infrastructure.committed_changes.fake_committed_changes import (
    FakeCommittedChanges,
)
from codetaster.infrastructure.committed_changes.git_committed_changes import (
    GitArguments,
    GitCommittedChanges,
)
from codetaster.infrastructure.external_tool.run_external_tool import ToolOutput


class FileText(RootModel[str]):
    @staticmethod
    def fake() -> FileText:
        return FileText("content\n")


type FileEdits = Mapping[RepositoryPath, FileText | None]
"""New content per path. `None` deletes the file."""


class Repository(Protocol):
    """A repository that tests build history in, read through `changes`."""

    changes: CommittedChanges
    checkout: CheckoutPath
    initial_branch: RevisionName

    def commit(self, edits: FileEdits) -> CommitSha: ...

    def create_branch(self, name: RevisionName) -> None:
        """Create `name` at HEAD and switch to it."""
        ...

    def switch_to(self, name: RevisionName) -> None: ...

    def leave_uncommitted_file(self) -> None: ...


class GitRepository(Repository):
    def __init__(self, root: Path) -> None:
        self.root = root
        self.changes = GitCommittedChanges()
        self.checkout = CheckoutPath(root)
        self.initial_branch = RevisionName("main")
        _ = self.git(
            GitArguments(
                ("init", "--quiet", f"--initial-branch={self.initial_branch.root}")
            )
        )

    def git(self, arguments: GitArguments) -> ToolOutput:
        completed = subprocess.run(
            [
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.com",
                "-c",
                "commit.gpgsign=false",
                "-c",
                "core.hooksPath=/dev/null",
                *arguments.root,
            ],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )
        return ToolOutput(completed.stdout.strip())

    @override
    def commit(self, edits: FileEdits) -> CommitSha:
        for path, text in edits.items():
            file = self.root / path.root
            if text is None:
                file.unlink()
            else:
                file.parent.mkdir(parents=True, exist_ok=True)
                _ = file.write_text(text.root)
        _ = self.git(GitArguments(("add", "--all")))
        _ = self.git(
            GitArguments(("commit", "--quiet", "--allow-empty", "--message=commit"))
        )
        return CommitSha(self.git(GitArguments(("rev-parse", "HEAD"))).root)

    @override
    def create_branch(self, name: RevisionName) -> None:
        _ = self.git(GitArguments(("switch", "--quiet", "--create", name.root)))

    @override
    def switch_to(self, name: RevisionName) -> None:
        _ = self.git(GitArguments(("switch", "--quiet", name.root)))

    @override
    def leave_uncommitted_file(self) -> None:
        _ = (self.root / "uncommitted.txt").write_text("")


class InMemoryRepository(Repository):
    def __init__(self) -> None:
        self.initial_branch = RevisionName("main")
        self.fake = FakeCommittedChanges(self.initial_branch)
        self.changes = self.fake
        self.checkout = CheckoutPath.fake()

    @override
    def commit(self, edits: FileEdits) -> CommitSha:
        return self.fake.commit(
            {
                path: None
                if text is None
                else BlobSha(hashlib.sha1(text.root.encode()).hexdigest())
                for path, text in edits.items()
            }
        )

    @override
    def create_branch(self, name: RevisionName) -> None:
        self.fake.create_branch(name)

    @override
    def switch_to(self, name: RevisionName) -> None:
        self.fake.switch_to(name)

    @override
    def leave_uncommitted_file(self) -> None:
        self.fake.working_tree = WorkingTreeState.DIRTY


@pytest.fixture(params=["git", "fake"])
def repository(request: pytest.FixtureRequest, tmp_path: Path) -> Repository:
    if request.param == "git":
        return GitRepository(tmp_path)
    return InMemoryRepository()


def change_from_main(
    repository: Repository, edits: FileEdits, base_edits: FileEdits | None = None
) -> CommittedChange:
    """Commit `base_edits` on the initial branch, branch off, commit `edits`, and read the change."""
    _ = repository.commit(base_edits or {RepositoryPath("README.md"): FileText.fake()})
    repository.create_branch(RevisionName("feature"))
    _ = repository.commit(edits)
    match repository.changes.read_committed_change(
        repository.checkout, repository.initial_branch
    ):
        case Ok(change):
            return change
        case Err(error):
            raise error


def test_change_types(repository: Repository) -> None:
    added = RepositoryPath("added.py")
    modified = RepositoryPath("modified.py")
    deleted = RepositoryPath("deleted.py")
    expected = {
        added: ChangeType.ADDED,
        modified: ChangeType.MODIFIED,
        deleted: ChangeType.DELETED,
    }

    change = change_from_main(
        repository,
        edits={added: FileText("new\n"), modified: FileText("v2\n"), deleted: None},
        base_edits={modified: FileText("v1\n"), deleted: FileText("old\n")},
    )

    assert {file.path(): file.change_type() for file in change.files.root} == expected


def test_a_moved_file_is_a_rename_with_the_same_blob(repository: Repository) -> None:
    old_path = RepositoryPath("old/name.py")
    new_path = RepositoryPath("new/name.py")
    text = FileText("a file long enough that git detects the rename\n" * 5)

    change = change_from_main(
        repository, edits={old_path: None, new_path: text}, base_edits={old_path: text}
    )

    [file] = change.files.root
    assert file.change_type() is ChangeType.RENAMED
    assert file.path() == new_path
    assert file.previous_path() == old_path
    assert file.before is not None
    assert file.after is not None
    assert file.before.blob == file.after.blob


def test_a_modified_file_has_different_blobs(repository: Repository) -> None:
    path = RepositoryPath("file.py")

    change = change_from_main(
        repository,
        edits={path: FileText("v2\n")},
        base_edits={path: FileText("v1\n")},
    )

    [file] = change.files.root
    assert file.before is not None
    assert file.after is not None
    assert file.before.blob != file.after.blob


def test_same_content_has_the_same_blob_across_files(repository: Repository) -> None:
    text = FileText.fake()

    change = change_from_main(
        repository,
        edits={RepositoryPath("one.py"): text, RepositoryPath("two.py"): text},
    )

    assert len({file.after.blob for file in change.files.root if file.after}) == 1


def test_only_commits_since_the_merge_base_count(repository: Repository) -> None:
    main = repository.initial_branch
    feature = RevisionName("feature")
    on_feature = RepositoryPath("feature.py")
    branch_point = repository.commit({RepositoryPath("README.md"): FileText.fake()})
    repository.create_branch(feature)
    head = repository.commit({on_feature: FileText.fake()})
    repository.switch_to(main)
    _ = repository.commit({RepositoryPath("main.py"): FileText.fake()})
    repository.switch_to(feature)

    result = repository.changes.read_committed_change(repository.checkout, main)

    match result:
        case Ok(change):
            assert change.base == main
            assert change.merge_base == branch_point
            assert change.head == head
            assert [file.path() for file in change.files.root] == [on_feature]
        case Err(error):
            raise error


def test_no_commits_since_the_base_is_no_change(repository: Repository) -> None:
    _ = repository.commit({RepositoryPath("README.md"): FileText.fake()})
    repository.create_branch(RevisionName("feature"))

    result = repository.changes.read_committed_change(
        repository.checkout, repository.initial_branch
    )

    match result:
        case Ok(change):
            assert change.files.root == ()
        case Err(error):
            raise error


def test_an_unknown_base_is_an_error_naming_it(repository: Repository) -> None:
    unknown = RevisionName("no-such-branch")
    _ = repository.commit({RepositoryPath("README.md"): FileText.fake()})

    result = repository.changes.read_committed_change(repository.checkout, unknown)

    match result:
        case Err(UnknownRevisionError() as error):
            assert error.revision == unknown
        case _:
            raise AssertionError(result)


def test_working_tree_is_clean_after_committing(repository: Repository) -> None:
    _ = repository.commit({RepositoryPath("README.md"): FileText.fake()})

    assert repository.changes.read_working_tree_state(repository.checkout) == Ok(
        WorkingTreeState.CLEAN
    )


def test_an_untracked_file_makes_the_working_tree_dirty(
    repository: Repository,
) -> None:
    _ = repository.commit({RepositoryPath("README.md"): FileText.fake()})
    repository.leave_uncommitted_file()

    assert repository.changes.read_working_tree_state(repository.checkout) == Ok(
        WorkingTreeState.DIRTY
    )


def test_files_are_ordered_by_path(repository: Repository) -> None:
    # A rename sorts by its new path, not the old one.
    text = FileText("a file long enough that git detects the rename\n" * 5)
    expected = [RepositoryPath("m/added.py"), RepositoryPath("z/renamed.py")]

    change = change_from_main(
        repository,
        edits={
            RepositoryPath("a/original.py"): None,
            RepositoryPath("z/renamed.py"): text,
            RepositoryPath("m/added.py"): FileText.fake(),
        },
        base_edits={RepositoryPath("a/original.py"): text},
    )

    assert [file.path() for file in change.files.root] == expected
