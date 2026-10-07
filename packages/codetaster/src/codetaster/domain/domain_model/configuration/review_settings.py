from typing import override

from pydantic import BaseModel, ConfigDict, Field

from codetaster.domain.domain_model.configuration.settings import Settings
from codetaster.domain.domain_model.review.changes import RepositoryPath, RevisionName
from codetaster.domain.domain_model.review.path_rules import PathRules
from codetaster.domain.domain_model.review.probability import Probability
from codetaster.domain.domain_model.review.top_rated import TopRatedPercentage


class ReviewSettings(BaseModel):
    """The `[review]` section, which only the project config may contain."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    base_branch: RevisionName = Field(
        description="The branch changes are compared against. `--base` overrides it."
    )
    base_probability: Probability = Field(
        description="The probability, from 0 to 1, that a changed file needs review."
    )
    top_rated_percentage: TopRatedPercentage = Field(
        default=TopRatedPercentage(20),
        description="The percentage, from 0 to 100, of changed files that need "
        "review: those with the highest AI ratings. `--top-rated-percentage` "
        "overrides it.",
    )
    ratings_path: RepositoryPath = Field(
        default=RepositoryPath(".codetaster/ratings.json"),
        description="The AI ratings file, relative to the repository root. "
        "Usually gitignored. `check` never lists it.",
    )
    path_rules: PathRules = Field(
        default=PathRules(()),
        description="Base probabilities for the files whose path matches a glob, "
        "in place of base_probability. Write each as a [[review.path_rules]] table "
        'with a pattern, such as "*.toml" or "src/**/*.sql", and a probability. '
        "A pattern without / matches the file name in any directory. When several "
        "match, the last one wins.",
    )

    @staticmethod
    def fake() -> ReviewSettings:
        return ReviewSettings(
            base_branch=RevisionName.fake(),
            base_probability=Probability.fake(),
            top_rated_percentage=TopRatedPercentage.fake(),
            ratings_path=RepositoryPath(".codetaster/ratings.json"),
            path_rules=PathRules(()),
        )


class ProjectSettings(Settings):
    """The settings a project config may contain: every setting, plus `[review]`."""

    review: ReviewSettings | None = None

    @override
    @staticmethod
    def fake() -> ProjectSettings:
        return ProjectSettings(
            log_format=Settings.fake().log_format, review=ReviewSettings.fake()
        )
