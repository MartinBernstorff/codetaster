import subprocess
from pathlib import Path

from codetaster_cli.domain.domain_model.checkout import CheckoutPath
from codetaster_cli.infrastructure.git_hooks.lefthook_git_hooks import (
    LefthookGitHooks,
)


def test_install_writes_and_uninstall_removes_the_pre_commit_hook(
    tmp_path: Path,
) -> None:
    _ = subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    _ = (tmp_path / "lefthook.yml").write_text(
        "pre-commit:\n  jobs:\n    - run: 'true'\n"
    )
    checkout = CheckoutPath(tmp_path)
    hook = tmp_path / ".git" / "hooks" / "pre-commit"

    _ = LefthookGitHooks().install_hooks(checkout)
    assert hook.exists()

    _ = LefthookGitHooks().uninstall_hooks(checkout)
    assert not hook.exists()
