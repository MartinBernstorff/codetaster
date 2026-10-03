"""Contract for GitHooks, run against every implementation."""

import subprocess
from pathlib import Path

import pytest
from safe_result import Ok

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.secondary_ports.git_hooks import GitHooks
from codetaster.infrastructure.fakes.call_log import CallLog
from codetaster.infrastructure.git_hooks.fake_git_hooks import FakeGitHooks
from codetaster.infrastructure.git_hooks.lefthook_git_hooks import (
    LefthookGitHooks,
)


@pytest.fixture(params=["lefthook", "fake"])
def hooks(request: pytest.FixtureRequest) -> GitHooks:
    if request.param == "lefthook":
        return LefthookGitHooks()
    return FakeGitHooks(CallLog.fake())


@pytest.fixture
def repository(tmp_path: Path) -> CheckoutPath:
    _ = subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    _ = (tmp_path / "lefthook.yml").write_text(
        "pre-commit:\n  jobs:\n    - run: 'true'\n"
    )
    return CheckoutPath(tmp_path)


def test_installing_twice_succeeds(hooks: GitHooks, repository: CheckoutPath) -> None:
    assert hooks.install_hooks(repository) == Ok(None)
    assert hooks.install_hooks(repository) == Ok(None)
