"""A ratings file with every changed file listed and nothing rated yet.

An agent fills in the summary, the categories, and `probability` and `category`
for each entry. Until it does, the template does not parse as a ratings file.
Each entry's placeholder annotation shows the shape of one; the agent fills it in
or removes it, and one left blank is ignored.
"""

from pydantic import BaseModel, ConfigDict

from codetaster.domain.domain_model.review.changes import (
    BlobSha,
    FileChanges,
    RepositoryPath,
)
from codetaster.domain.domain_model.review.ratings import AnnotationSide, RatingTarget


class BlankAnnotation(BaseModel):
    """A placeholder that shows the shape of an annotation, and its default side."""

    model_config = ConfigDict(frozen=True)

    side: AnnotationSide = AnnotationSide.AFTER
    line: None = None
    text: None = None

    @staticmethod
    def fake() -> BlankAnnotation:
        return BlankAnnotation()


class BlankRating(BaseModel):
    """A ratings file entry with the file filled in and the rating left blank."""

    model_config = ConfigDict(frozen=True)

    path: RepositoryPath
    blob: BlobSha | None
    probability: None = None
    category: None = None
    annotations: tuple[BlankAnnotation, ...] = (BlankAnnotation(),)

    @staticmethod
    def fake() -> BlankRating:
        return BlankRating.of_target(RatingTarget.fake())

    @staticmethod
    def of_target(target: RatingTarget) -> BlankRating:
        return BlankRating(path=target.path, blob=target.blob)

    def target(self) -> RatingTarget:
        return RatingTarget(path=self.path, blob=self.blob)


class BlankCategory(BaseModel):
    """A placeholder that shows the shape of a category."""

    model_config = ConfigDict(frozen=True)

    name: None = None
    description: None = None

    @staticmethod
    def fake() -> BlankCategory:
        return BlankCategory()


class RatingsTemplate(BaseModel):
    model_config = ConfigDict(frozen=True)

    summary: None = None
    categories: tuple[BlankCategory, ...] = (BlankCategory(),)
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
