import pytest
from pydantic import ValidationError

from codetaster.domain.domain_model.review.changes import RepositoryPath
from codetaster.domain.domain_model.review.path_rules import (
    PathPattern,
    PathRule,
    PathRules,
)
from codetaster.domain.domain_model.review.probability import Probability


@pytest.mark.parametrize(
    ("pattern", "path"),
    [
        ("*.toml", "pyproject.toml"),
        ("*.toml", "docs/site/config.toml"),
        ("README.md", "packages/app/README.md"),
        ("src/*.py", "src/module.py"),
        ("src/**", "src/a/b/module.py"),
        ("src/**/*.sql", "src/schema.sql"),
        ("src/**/*.sql", "src/db/migrations/0001.sql"),
        ("*.toml", "./pyproject.toml"),
    ],
)
def test_pattern_matches(pattern: str, path: str) -> None:
    assert PathPattern(pattern).matches(RepositoryPath(path))


@pytest.mark.parametrize(
    ("pattern", "path"),
    [
        ("*.toml", "pyproject.toml.bak"),
        ("src/*.py", "src/nested/module.py"),
        ("src/*.py", "lib/src/module.py"),
        ("README.md", "readme.md"),
    ],
)
def test_pattern_does_not_match(pattern: str, path: str) -> None:
    assert not PathPattern(pattern).matches(RepositoryPath(path))


def test_absolute_pattern_is_invalid() -> None:
    with pytest.raises(ValidationError):
        _ = PathPattern("/pyproject.toml")


def test_empty_pattern_is_invalid() -> None:
    with pytest.raises(ValidationError):
        _ = PathPattern("")


def test_the_last_matching_rule_wins() -> None:
    general = PathRule(pattern=PathPattern("*.toml"), probability=Probability(1))
    specific = PathRule(pattern=PathPattern("uv.toml"), probability=Probability(0))
    rules = PathRules((general, specific))

    assert rules.rule_for(RepositoryPath("uv.toml")) == specific
    assert rules.rule_for(RepositoryPath("pyproject.toml")) == general


def test_no_rule_for_an_unmatched_path() -> None:
    assert PathRules.fake().rule_for(RepositoryPath("module.py")) is None
