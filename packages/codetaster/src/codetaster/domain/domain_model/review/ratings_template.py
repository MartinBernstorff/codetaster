"""A ratings file with every changed file listed and nothing rated yet.

An agent fills in `probability` and `reason` for each entry. Until it does, the
template does not parse as a ratings file.
"""

from pydantic import BaseModel, ConfigDict

from codetaster.domain.domain_model.review.changes import (
    BlobSha,
    FileChanges,
    RepositoryPath,
)
from codetaster.domain.domain_model.review.ratings import RatingTarget


class BlankRating(BaseModel):
    """A ratings file entry with the file filled in and the rating left blank."""

    model_config = ConfigDict(frozen=True)

    path: RepositoryPath
    blob: BlobSha | None
    probability: None = None
    reason: None = None

    @staticmethod
    def fake() -> BlankRating:
        return BlankRating.of_target(RatingTarget.fake())

    @staticmethod
    def of_target(target: RatingTarget) -> BlankRating:
        return BlankRating(path=target.path, blob=target.blob)

    def target(self) -> RatingTarget:
        return RatingTarget(path=self.path, blob=self.blob)


class RatingsTemplate(BaseModel):
    model_config = ConfigDict(frozen=True)

    ratings: tuple[BlankRating, ...]

    @staticmethod
    def fake() -> RatingsTemplate:
        return RatingsTemplate(ratings=(BlankRating.fake(),))

    @staticmethod
    def of_changes(changes: FileChanges) -> RatingsTemplate:
        """One blank rating per change, in the order of `changes`."""
        return RatingsTemplate(
            ratings=tuple(
                BlankRating.of_target(RatingTarget.of_change(change))
                for change in changes.root
            )
        )
