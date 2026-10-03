from typing import override

from pydantic import BaseModel, ConfigDict, Field

from codetaster.domain.domain_model.configuration.settings import Settings
from codetaster.domain.domain_model.review.changes import RevisionName
from codetaster.domain.domain_model.review.sampling import Probability


class ReviewSettings(BaseModel):
    """The `[review]` section, which only the project config may contain."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    base_branch: RevisionName = Field(
        description="The branch changes are compared against. `--base` overrides it."
    )
    base_probability: Probability = Field(
        description="The probability, from 0 to 1, that a changed file needs review."
    )

    @staticmethod
    def fake() -> ReviewSettings:
        return ReviewSettings(
            base_branch=RevisionName.fake(), base_probability=Probability.fake()
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
