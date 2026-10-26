"""A ratings file with every changed file listed and nothing rated yet.

An agent fills in the summary, the categories, and for each entry its `category`
and each hunk's `probability`. Until it does, the template does not parse as a
ratings file.
Each entry's placeholder annotation shows the shape of one; the agent fills it in
or removes it, and one left blank is ignored.
"""

from pydantic import BaseModel, ConfigDict

from codetaster.domain.domain_model.review.changes import (
    BlobSha,
    ChangeLineHunks,
    FileChange,
    FileChanges,
    LineHunk,
    LineSpan,
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


class BlankHunk(BaseModel):
    """A hunk with its lines filled in and its probability left blank.

    Without lines for a file whose change has none, e.g. a binary file.
    """

    model_config = ConfigDict(frozen=True)

    before: LineSpan | None
    after: LineSpan | None
    probability: None = None

    @staticmethod
    def fake() -> BlankHunk:
        return BlankHunk.of_line_hunk(LineHunk.fake())

    @staticmethod
    def of_line_hunk(hunk: LineHunk | None) -> BlankHunk:
        """Without lines if `hunk` is `None`, for the whole change."""
        if hunk is None:
            return BlankHunk(before=None, after=None)
        return BlankHunk(before=hunk.before, after=hunk.after)


class BlankRating(BaseModel):
    """A ratings file entry with the file filled in and the rating left blank."""

    model_config = ConfigDict(frozen=True)

    path: RepositoryPath
    blob: BlobSha | None
    category: None = None
    hunks: tuple[BlankHunk, ...]
    annotations: tuple[BlankAnnotation, ...] = (BlankAnnotation(),)

    @staticmethod
    def fake() -> BlankRating:
        target = RatingTarget.fake()
        return BlankRating(
            path=target.path, blob=target.blob, hunks=(BlankHunk.fake(),)
        )

    @staticmethod
    def of_change(
        change: FileChange, hunks: tuple[LineHunk | None, ...]
    ) -> BlankRating:
        """One blank hunk per hunk in `hunks`, as `ChangeLineHunks.hunks_to_rate`
        lists them."""
        target = RatingTarget.of_change(change)
        return BlankRating(
            path=target.path,
            blob=target.blob,
            hunks=tuple(BlankHunk.of_line_hunk(hunk) for hunk in hunks),
        )

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
    def of_changes(changes: FileChanges, hunks: ChangeLineHunks) -> RatingsTemplate:
        """One blank rating per change, in the order of `changes`, with the
        change's hunks in `hunks`."""
        return RatingsTemplate(
            ratings=tuple(
                BlankRating.of_change(change, hunks.hunks_to_rate(change))
                for change in changes.root
            )
        )
