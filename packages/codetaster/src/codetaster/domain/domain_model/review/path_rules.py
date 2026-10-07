"""Path rules: a base probability for the files whose path matches a glob.

In the project config:

    [[review.path_rules]]
    pattern = "*.toml"
    probability = 1.0
"""

from pathlib import PurePosixPath
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator

from codetaster.domain.domain_model.review.changes import RepositoryPath
from codetaster.domain.domain_model.review.probability import Probability


class PathPattern(RootModel[Annotated[str, Field(min_length=1)]]):
    """A glob over repository paths.

    Without a `/`, it matches the file name in any directory, so `*.toml` matches
    `pyproject.toml` and `docs/site.toml`. With a `/`, it matches the whole path
    from the repository root. `*` matches within one directory, `**` any number
    of directories.
    """

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def is_relative(self) -> Self:
        if self.root.startswith("/"):
            msg = "a pattern is relative to the repository root, so it cannot start with /"
            raise ValueError(msg)
        return self

    @staticmethod
    def fake() -> PathPattern:
        return PathPattern("*.toml")

    def matches(self, path: RepositoryPath) -> bool:
        pattern = self.root if "/" in self.root else f"**/{self.root}"
        return PurePosixPath(path.normalised().root).full_match(pattern)


class PathRule(BaseModel):
    """Files whose path matches `pattern` are sampled at `probability`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pattern: PathPattern
    probability: Probability

    @staticmethod
    def fake() -> PathRule:
        return PathRule(pattern=PathPattern.fake(), probability=Probability(1.0))


class PathRules(RootModel[tuple[PathRule, ...]]):
    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> PathRules:
        return PathRules((PathRule.fake(),))

    def rule_for(self, path: RepositoryPath) -> PathRule | None:
        """The last rule matching `path`, so a later, narrower rule can override."""
        return next(
            (rule for rule in reversed(self.root) if rule.pattern.matches(path)), None
        )
