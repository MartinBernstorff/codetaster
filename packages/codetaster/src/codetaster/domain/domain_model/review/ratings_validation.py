"""Problems that stop a ratings file from rating exactly the current change."""

from collections import Counter

from pydantic import BaseModel, ConfigDict, RootModel

from codetaster.domain.domain_model.configuration.errors import ErrorReason
from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.domain_model.review.changes import FileChanges
from codetaster.domain.domain_model.review.ratings import RatingsFile, RatingTarget


class MissingRatingsFile(BaseModel):
    """No ratings file exists where `[review] ratings_path` points."""

    model_config = ConfigDict(frozen=True)

    location: Location

    @staticmethod
    def fake() -> MissingRatingsFile:
        return MissingRatingsFile(location=Location.fake())


class InvalidRatingsFile(BaseModel):
    """The ratings file cannot be read or does not match the format."""

    model_config = ConfigDict(frozen=True)

    location: Location
    reason: ErrorReason

    @staticmethod
    def fake() -> InvalidRatingsFile:
        return InvalidRatingsFile(location=Location.fake(), reason=ErrorReason.fake())


class UnratedFile(BaseModel):
    """A changed file with no rating for its current version."""

    model_config = ConfigDict(frozen=True)

    target: RatingTarget

    @staticmethod
    def fake() -> UnratedFile:
        return UnratedFile(target=RatingTarget.fake())


class StaleRating(BaseModel):
    """A rating for a changed file's path, but for another version of it."""

    model_config = ConfigDict(frozen=True)

    rating: RatingTarget
    current: RatingTarget

    @staticmethod
    def fake() -> StaleRating:
        current = RatingTarget.fake()
        return StaleRating(
            rating=current.model_copy(update={"blob": None}), current=current
        )


class UnknownRating(BaseModel):
    """A rating for a path that is not changed."""

    model_config = ConfigDict(frozen=True)

    rating: RatingTarget

    @staticmethod
    def fake() -> UnknownRating:
        return UnknownRating(rating=RatingTarget.fake())


class DuplicateRating(BaseModel):
    """More than one rating for the same file version."""

    model_config = ConfigDict(frozen=True)

    target: RatingTarget

    @staticmethod
    def fake() -> DuplicateRating:
        return DuplicateRating(target=RatingTarget.fake())


RatingProblem = (
    MissingRatingsFile
    | InvalidRatingsFile
    | UnratedFile
    | StaleRating
    | UnknownRating
    | DuplicateRating
)


class RatingProblems(RootModel[tuple[RatingProblem, ...]]):
    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> RatingProblems:
        return RatingProblems((UnratedFile.fake(),))


def find_rating_problems(changes: FileChanges, ratings: RatingsFile) -> RatingProblems:
    """Compare the ratings with the changes, which should be rated exactly once each.

    A changed file with a stale rating is reported as stale, not also as unrated.
    """
    current_by_path = {
        target.path: target
        for target in (RatingTarget.of_change(change) for change in changes.root)
    }
    rated = Counter(rating.target() for rating in ratings.ratings)
    stale = tuple(
        StaleRating(rating=target, current=current_by_path[target.path])
        for target in rated
        if target.path in current_by_path and current_by_path[target.path] != target
    )
    stale_paths = {problem.rating.path for problem in stale}
    unrated = tuple(
        UnratedFile(target=target)
        for target in current_by_path.values()
        if target not in rated and target.path not in stale_paths
    )
    unknown = tuple(
        UnknownRating(rating=target)
        for target in rated
        if target.path not in current_by_path
    )
    duplicates = tuple(
        DuplicateRating(target=target) for target, count in rated.items() if count > 1
    )
    return RatingProblems((*unrated, *stale, *unknown, *duplicates))
