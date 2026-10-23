"""AI ratings: how likely each changed file is to need human review.

The ratings file is JSON:

    {
      "summary": "Markdown summary of the PR, referring to its categories",
      "categories": [
        {
          "name": "Retry failed payments",
          "description": "Markdown description of this part of the PR"
        }
      ],
      "ratings": [
        {
          "path": "src/module.py",
          "blob": "<after-blob SHA, or null for a deleted file>",
          "probability": 0.8,
          "category": "Retry failed payments",
          "annotations": [
            {"side": "after", "line": 12, "text": "Moved from old.py."}
          ]
        }
      ]
    }

A rating applies to a file's change only when both `path` and `blob` match it,
so editing a file makes its rating stale, and its annotations with it.
`annotations` is optional. An annotation with a null `line` and `text`, as the
template shows, is ignored.
"""

from enum import StrEnum
from typing import Annotated, override

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    RootModel,
    ValidationError,
    field_validator,
)
from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.configuration.errors import ErrorReason
from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.domain_model.review.changes import (
    BlobSha,
    FileChange,
    RepositoryPath,
)
from codetaster.domain.domain_model.review.probability import Probability


class RatingCategory(RootModel[Annotated[str, Field(min_length=1)]]):
    """Which part of the PR a file belongs to.

    Each file has exactly one category.
    """

    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return self.root

    @staticmethod
    def fake() -> RatingCategory:
        return RatingCategory("Retry failed payments")


class PullRequestSummary(RootModel[Annotated[str, Field(min_length=1)]]):
    """Markdown: what the PR does, referring to its categories by name."""

    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return self.root

    @staticmethod
    def fake() -> PullRequestSummary:
        return PullRequestSummary("Retries failed payments.")


class CategoryDescription(RootModel[Annotated[str, Field(min_length=1)]]):
    """Markdown: what a category's files change, and why."""

    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return self.root

    @staticmethod
    def fake() -> CategoryDescription:
        return CategoryDescription("Retries a payment when the provider times out.")


class DescribedCategory(BaseModel):
    """A category of the PR and its description."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: RatingCategory = Field(
        description="What ratings put in `category` to place a file in it."
    )
    description: CategoryDescription = Field(
        description="Markdown: what the category's files change, and why."
    )

    @staticmethod
    def fake() -> DescribedCategory:
        return DescribedCategory(
            name=RatingCategory.fake(), description=CategoryDescription.fake()
        )


class PullRequestOverview(BaseModel):
    """The summary of the PR, and its categories in the order to show them."""

    model_config = ConfigDict(frozen=True)

    summary: PullRequestSummary
    categories: tuple[DescribedCategory, ...]

    @staticmethod
    def fake() -> PullRequestOverview:
        return PullRequestOverview(
            summary=PullRequestSummary.fake(), categories=(DescribedCategory.fake(),)
        )


class AnnotationSide(StrEnum):
    """Which version of a file an annotation's line is in."""

    BEFORE = "before"
    AFTER = "after"


class LineNumber(RootModel[Annotated[int, Field(ge=1)]]):
    """A line in one version of a file, counting from 1."""

    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return str(self.root)

    @staticmethod
    def fake() -> LineNumber:
        return LineNumber(1)


class AnnotationText(RootModel[Annotated[str, Field(min_length=1)]]):
    """Markdown: a note for the reviewer about a line."""

    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return self.root

    @staticmethod
    def fake() -> AnnotationText:
        return AnnotationText("Moved from old.py.")


class LineAnnotation(BaseModel):
    """A note on one line of a rated file, shown to the reviewer in the diff."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    side: AnnotationSide = Field(
        default=AnnotationSide.AFTER,
        description="before or after: which version of the file `line` is in.",
    )
    line: LineNumber = Field(
        description="The line, counting from 1, in that version of the file."
    )
    text: AnnotationText = Field(
        description="Markdown: a note for the reviewer, e.g. that the content was "
        "moved from another file."
    )

    @staticmethod
    def fake() -> LineAnnotation:
        return LineAnnotation(
            side=AnnotationSide.AFTER,
            line=LineNumber.fake(),
            text=AnnotationText.fake(),
        )


class RatingTarget(BaseModel):
    """The file version a rating is for: the path and after-blob of a change.

    `blob` is `None` for a deleted file, which has no after version.
    """

    model_config = ConfigDict(frozen=True)

    path: RepositoryPath
    blob: BlobSha | None

    @staticmethod
    def fake() -> RatingTarget:
        return RatingTarget.of_change(FileChange.fake())

    @staticmethod
    def of_change(change: FileChange) -> RatingTarget:
        return RatingTarget(
            path=change.path(),
            blob=None if change.after is None else change.after.blob,
        )


class FileRating(BaseModel):
    """One entry in the ratings file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: RepositoryPath = Field(
        description="From the repository root, with / separators. A renamed "
        "file's new path, a deleted file's old path."
    )
    blob: BlobSha | None = Field(
        description="The file's blob SHA at HEAD (`git rev-parse HEAD:<path>`), "
        "or null for a deleted file."
    )
    probability: Probability = Field(
        description="From 0 to 1, how likely the file is to need human review."
    )
    category: RatingCategory = Field(
        description="Which part of the PR the file belongs to, e.g. a feature, "
        "refactor or move. The name of one of `categories`."
    )
    annotations: tuple[LineAnnotation, ...] = Field(
        default=(),
        description="Notes for the reviewer on lines of this version of the file. "
        "Optional.",
    )

    @field_validator("annotations", mode="before")
    @classmethod
    def drop_blank_annotations(cls, annotations: JsonValue) -> JsonValue:
        """Ignore the template's placeholder, so leaving it in is harmless."""
        if not isinstance(annotations, list):
            return annotations
        return [
            annotation
            for annotation in annotations
            if not (
                isinstance(annotation, dict)
                and "line" in annotation
                and "text" in annotation
                and annotation["line"] is None
                and annotation["text"] is None
            )
        ]

    @staticmethod
    def fake() -> FileRating:
        """Without annotations, so the fake rating is valid for any change."""
        target = RatingTarget.fake()
        return FileRating(
            path=target.path,
            blob=target.blob,
            probability=Probability.fake(),
            category=RatingCategory.fake(),
            annotations=(),
        )

    def target(self) -> RatingTarget:
        return RatingTarget(path=self.path, blob=self.blob)


class FileRatings(RootModel[tuple[FileRating, ...]]):
    """Ratings for files not in the change are ignored."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> FileRatings:
        return FileRatings((FileRating.fake(),))

    def rating_for(self, change: FileChange) -> FileRating | None:
        """The matching rating, or `None`. Of several matches, the highest wins."""
        target = RatingTarget.of_change(change)
        matching = sorted(
            (rating for rating in self.root if rating.target() == target),
            key=lambda rating: rating.probability.root,
        )
        return matching[-1] if matching else None


class RatingsFile(BaseModel):
    """The ratings file's content."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    summary: PullRequestSummary = Field(
        description="Markdown: what the PR does, referring to its categories by name."
    )
    categories: tuple[DescribedCategory, ...] = Field(
        description="The parts of the PR, in the order a reviewer should read them."
    )
    ratings: FileRatings

    @staticmethod
    def fake() -> RatingsFile:
        return RatingsFile(
            summary=PullRequestSummary.fake(),
            categories=(DescribedCategory.fake(),),
            ratings=FileRatings.fake(),
        )

    def overview(self) -> PullRequestOverview:
        return PullRequestOverview(summary=self.summary, categories=self.categories)


class RatingsFileContent(RootModel[str]):
    """The raw text of a ratings file."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> RatingsFileContent:
        return RatingsFileContent(RatingsFile.fake().model_dump_json(indent=2))


class RatingsFileError(Exception):
    """A ratings file exists but cannot be read or does not match the format."""

    def __init__(self, location: Location, reason: ErrorReason) -> None:
        super().__init__(f"invalid ratings file {location.root}: {reason.root}")
        self.location = location
        self.reason = reason

    @staticmethod
    def fake() -> RatingsFileError:
        return RatingsFileError(Location.fake(), ErrorReason.fake())


def parse_ratings_file(
    content: RatingsFileContent, location: Location
) -> Result[RatingsFile, RatingsFileError]:
    try:
        return Ok(RatingsFile.model_validate_json(content.root))
    except ValidationError as error:
        return Err(RatingsFileError(location, ErrorReason(str(error))))


def ratings_file_location(checkout: CheckoutPath, path: RepositoryPath) -> Location:
    """`[review] ratings_path` is relative to the repository root."""
    return Location(checkout.root / path.root)
