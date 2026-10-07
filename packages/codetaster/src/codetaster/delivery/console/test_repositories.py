"""A git repository for command tests, shared by the tests in this folder."""

import subprocess
from pathlib import Path

from pydantic import RootModel

from codetaster.infrastructure.committed_changes.git_committed_changes import (
    GitArguments,
)


class TomlText(RootModel[str]):
    @staticmethod
    def fake() -> TomlText:
        return TomlText('[review]\nbase_branch = "main"\nbase_probability = 1\n')


class Repository:
    """A repository with a commit on main, and a feature branch adding a file."""

    def __init__(self, root: Path, project_config: TomlText | None) -> None:
        self.root = root
        if project_config is not None:
            _ = (root / "codetaster.toml").write_text(project_config.root)
        self.git(GitArguments(("init", "--quiet", "--initial-branch=main")))
        self.git(GitArguments(("add", "--all")))
        self.git(GitArguments(("commit", "--quiet", "--allow-empty", "--message=base")))
        self.git(GitArguments(("switch", "--quiet", "--create", "feature")))
        _ = (root / "feature.py").write_text("")
        self.git(GitArguments(("add", "--all")))
        self.git(GitArguments(("commit", "--quiet", "--message=feature")))

    def git(self, arguments: GitArguments) -> None:
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
            cwd=self.root,
            check=True,
            capture_output=True,
        )


class CliOptions(RootModel[tuple[str, ...]]):
    @staticmethod
    def fake() -> CliOptions:
        return CliOptions(())
