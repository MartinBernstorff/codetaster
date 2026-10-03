import subprocess
from pathlib import Path

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.infrastructure.git_hooks.lefthook_git_hooks import (
    LefthookGitHooks,
)


def test_install_writes_the_pre_commit_hook(tmp_path: Path) -> None:
    _ = subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    _ = (tmp_path / "lefthook.yml").write_text(
        "pre-commit:\n  jobs:\n    - run: 'true'\n"
    )

    pre_commit_hook = tmp_path / ".git" / "hooks" / "pre-commit"

    _ = LefthookGitHooks().install_hooks(CheckoutPath(tmp_path))

    assert pre_commit_hook.exists()
