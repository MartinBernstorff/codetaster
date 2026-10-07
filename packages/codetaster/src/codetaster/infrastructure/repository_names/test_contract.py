"""Contract for RepositoryNames, run against every implementation."""

import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest
from safe_result import Err, Ok

from codetaster.domain.domain_model.checkout import CheckoutPath, RepositoryName
from codetaster.domain.secondary_ports.repository_names import RepositoryNames
from codetaster.infrastructure.committed_changes.git_committed_changes import (
    GitArguments,
)
from codetaster.infrastructure.repository_names.fake_repository_names import (
    FakeRepositoryNames,
)
from codetaster.infrastructure.repository_names.git_repository_names import (
    GitRepositoryNames,
    repository_name_from_common_directory,
)


@dataclass(frozen=True)
class Repositories:
    """A repository called `name`, with a worktree in a differently named directory."""

    names: RepositoryNames
    name: RepositoryName
    main_checkout: CheckoutPath
    worktree: CheckoutPath
    outside: CheckoutPath


def git(checkout: CheckoutPath, arguments: GitArguments) -> None:
    _ = subprocess.run(
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
        cwd=checkout.root,
        check=True,
        capture_output=True,
    )


def git_repositories(parent: CheckoutPath, name: RepositoryName) -> Repositories:
    """Both checkouts and the outside directory are created in `parent`."""
    main_checkout = CheckoutPath(parent.root / name.root)
    worktree = CheckoutPath(parent.root / "worktrees" / "feature")
    outside = CheckoutPath(parent.root / "outside")
    main_checkout.root.mkdir()
    outside.root.mkdir()
    git(main_checkout, GitArguments(("init", "--quiet", "--initial-branch=main")))
    git(main_checkout, GitArguments(("commit", "--quiet", "--allow-empty", "-m", "c")))
    git(main_checkout, GitArguments(("worktree", "add", "--quiet", str(worktree))))
    return Repositories(
        names=GitRepositoryNames(),
        name=name,
        main_checkout=main_checkout,
        worktree=worktree,
        outside=outside,
    )


def fake_repositories(name: RepositoryName) -> Repositories:
    main_checkout = CheckoutPath(Path("/repos") / name.root)
    worktree = CheckoutPath(Path("/worktrees/feature"))
    return Repositories(
        names=FakeRepositoryNames({main_checkout: name, worktree: name}),
        name=name,
        main_checkout=main_checkout,
        worktree=worktree,
        outside=CheckoutPath(Path("/outside")),
    )


@pytest.fixture(params=["git", "fake"])
def repositories(request: pytest.FixtureRequest, tmp_path: Path) -> Repositories:
    name = RepositoryName("widget")
    if request.param == "git":
        return git_repositories(CheckoutPath(tmp_path), name)
    return fake_repositories(name)


def test_the_main_checkout_is_named_after_its_directory(
    repositories: Repositories,
) -> None:
    result = repositories.names.read_repository_name(repositories.main_checkout)

    assert result == Ok(repositories.name)


def test_a_worktree_has_its_repositorys_name(repositories: Repositories) -> None:
    result = repositories.names.read_repository_name(repositories.worktree)

    assert result == Ok(repositories.name)


def test_a_directory_outside_a_repository_is_an_error(
    repositories: Repositories,
) -> None:
    result = repositories.names.read_repository_name(repositories.outside)

    assert isinstance(result, Err)


@pytest.mark.parametrize(
    ("common_directory", "expected"),
    [
        ("/src/widget/.git", "widget"),
        ("/src/widget/.bare", "widget"),
        ("/src/widget.git", "widget"),
        ("/src/widget", "widget"),
    ],
)
def test_bare_and_non_bare_layouts_are_named_after_the_repository(
    common_directory: str, expected: str
) -> None:
    name = repository_name_from_common_directory(CheckoutPath(Path(common_directory)))

    assert name == RepositoryName(expected)
