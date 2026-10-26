"""Problems that stop a ratings file from rating exactly the current change."""

from collections import Counter
from collections.abc import Iterator

from pydantic import BaseModel, ConfigDict, RootModel

from codetaster.domain.domain_model.configuration.errors import ErrorReason
from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.domain_model.review.changes import (
    BlobLineCounts,
    BlobSha,
    ChangeLineHunks,
    FileChange,
    FileChanges,
    LineCount,
    LineHunk,
)
from codetaster.domain.domain_model.review.ratings import (
    AnnotationSide,
    FileRating,
    LineAnnotation,
    RatingCategory,
    RatingsFile,
    RatingTarget,
)


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


class UndeclaredCategory(BaseModel):
    """A category that ratings use but `categories` does not describe."""

    model_config = ConfigDict(frozen=True)

    category: RatingCategory

    @staticmethod
    def fake() -> UndeclaredCategory:
        return UndeclaredCategory(category=RatingCategory.fake())


class UnusedCategory(BaseModel):
    """A category in `categories` that no rating uses."""

    model_config = ConfigDict(frozen=True)

    category: RatingCategory

    @staticmethod
    def fake() -> UnusedCategory:
        return UnusedCategory(category=RatingCategory.fake())


class DuplicateCategory(BaseModel):
    """More than one entry in `categories` with the same name."""

    model_config = ConfigDict(frozen=True)

    category: RatingCategory

    @staticmethod
    def fake() -> DuplicateCategory:
        return DuplicateCategory(category=RatingCategory.fake())


class AnnotationOnMissingSide(BaseModel):
    """An annotation on the before side of an added file, or the after side of a
    deleted one."""

    model_config = ConfigDict(frozen=True)

    target: RatingTarget
    annotation: LineAnnotation

    @staticmethod
    def fake() -> AnnotationOnMissingSide:
        return AnnotationOnMissingSide(
            target=RatingTarget.fake(),
            annotation=LineAnnotation.fake().model_copy(
                update={"side": AnnotationSide.BEFORE}
            ),
        )


class AnnotationLineOutOfRange(BaseModel):
    """An annotation on a line past the end of its side of the file."""

    model_config = ConfigDict(frozen=True)

    target: RatingTarget
    annotation: LineAnnotation
    line_count: LineCount

    @staticmethod
    def fake() -> AnnotationLineOutOfRange:
        return AnnotationLineOutOfRange(
            target=RatingTarget.fake(),
            annotation=LineAnnotation.fake(),
            line_count=LineCount(0),
        )


class AnnotationOnUnreadableFile(BaseModel):
    """An annotation on a file version whose lines cannot be read, such as a
    submodule's."""

    model_config = ConfigDict(frozen=True)

    target: RatingTarget
    annotation: LineAnnotation

    @staticmethod
    def fake() -> AnnotationOnUnreadableFile:
        return AnnotationOnUnreadableFile(
            target=RatingTarget.fake(), annotation=LineAnnotation.fake()
        )


class HunkMismatch(BaseModel):
    """A rating whose hunks are not the changed lines of its file, as the template
    lists them.

    `None` stands for a hunk for the whole change, of a file without changed lines.
    """

    model_config = ConfigDict(frozen=True)

    target: RatingTarget
    rated: tuple[LineHunk | None, ...]
    changed: tuple[LineHunk | None, ...]

    @staticmethod
    def fake() -> HunkMismatch:
        return HunkMismatch(
            target=RatingTarget.fake(), rated=(None,), changed=(LineHunk.fake(),)
        )


FileRatingProblem = (
    MissingRatingsFile
    | InvalidRatingsFile
    | UnratedFile
    | StaleRating
    | UnknownRating
    | DuplicateRating
)

CategoryProblem = UndeclaredCategory | UnusedCategory | DuplicateCategory

AnnotationProblem = (
    AnnotationOnMissingSide | AnnotationLineOutOfRange | AnnotationOnUnreadableFile
)

RatingProblem = FileRatingProblem | HunkMismatch | CategoryProblem | AnnotationProblem


class RatingProblems(RootModel[tuple[RatingProblem, ...]]):
    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> RatingProblems:
        return RatingProblems((UnratedFile.fake(),))


def find_rating_problems(
    changes: FileChanges,
    ratings: RatingsFile,
    hunks: ChangeLineHunks,
    line_counts: BlobLineCounts,
) -> RatingProblems:
    """Compare the ratings with the changes, which should be rated exactly once each,
    hunk by hunk, check every category is declared once and used, and every
    annotation is on a line of its file.

    A changed file with a stale rating is reported as stale, not also as unrated.
    `hunks` has the changed lines of `changes`. `line_counts` needs the blobs
    `annotated_blobs` lists.
    """
    current_by_path = {
        target.path: target
        for target in (RatingTarget.of_change(change) for change in changes.root)
    }
    rated = Counter(rating.target() for rating in ratings.ratings.root)
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
    return RatingProblems(
        (
            *unrated,
            *stale,
            *unknown,
            *duplicates,
            *find_hunk_problems(changes, ratings, hunks),
            *find_category_problems(ratings),
            *find_annotation_problems(changes, ratings, line_counts),
        )
    )


def find_hunk_problems(
    changes: FileChanges, ratings: RatingsFile, hunks: ChangeLineHunks
) -> tuple[HunkMismatch, ...]:
    """Only the ratings `checked_ratings` lists are checked."""
    problems: list[HunkMismatch] = []
    for rating, change in checked_ratings(changes, ratings):
        changed = hunks.hunks_of(change) or (None,)
        if rating.line_hunks() != changed:
            problems.append(
                HunkMismatch(
                    target=rating.target(), rated=rating.line_hunks(), changed=changed
                )
            )
    return tuple(problems)


def find_category_problems(ratings: RatingsFile) -> tuple[CategoryProblem, ...]:
    declared = Counter(category.name for category in ratings.categories)
    used = dict.fromkeys(rating.category for rating in ratings.ratings.root)
    undeclared = tuple(
        UndeclaredCategory(category=category)
        for category in used
        if category not in declared
    )
    unused = tuple(
        UnusedCategory(category=category)
        for category in declared
        if category not in used
    )
    duplicates = tuple(
        DuplicateCategory(category=category)
        for category, count in declared.items()
        if count > 1
    )
    return (*undeclared, *unused, *duplicates)


def find_annotation_problems(
    changes: FileChanges, ratings: RatingsFile, line_counts: BlobLineCounts
) -> tuple[AnnotationProblem, ...]:
    """Only the annotations of the ratings `checked_ratings` lists are checked."""
    problems: list[AnnotationProblem] = []
    for rating, change in checked_ratings(changes, ratings):
        for annotation in rating.annotations:
            blob = annotated_blob(change, annotation.side)
            if blob is None:
                problems.append(
                    AnnotationOnMissingSide(
                        target=rating.target(), annotation=annotation
                    )
                )
                continue
            line_count = line_counts.root.get(blob)
            if line_count is None:
                problems.append(
                    AnnotationOnUnreadableFile(
                        target=rating.target(), annotation=annotation
                    )
                )
            elif annotation.line.root > line_count.root:
                problems.append(
                    AnnotationLineOutOfRange(
                        target=rating.target(),
                        annotation=annotation,
                        line_count=line_count,
                    )
                )
    return tuple(problems)


def annotated_blobs(changes: FileChanges, ratings: RatingsFile) -> tuple[BlobSha, ...]:
    """The file versions annotations are on, whose line counts validation needs.

    Each is listed once, in the order the ratings file first annotates it.
    """
    blobs: dict[BlobSha, None] = {}
    for rating, change in checked_ratings(changes, ratings):
        for annotation in rating.annotations:
            blob = annotated_blob(change, annotation.side)
            if blob is not None:
                blobs[blob] = None
    return tuple(blobs)


def checked_ratings(
    changes: FileChanges, ratings: RatingsFile
) -> Iterator[tuple[FileRating, FileChange]]:
    """The ratings whose hunks and annotations are checked, with their changes.

    A stale rating is not checked: the file is to be re-rated. Nor is a rating for
    an unchanged file, which is reported as unknown already. Of duplicate ratings,
    only the first is checked, so that its problems are reported once.
    """
    seen: set[RatingTarget] = set()
    for rating in ratings.ratings.root:
        target = rating.target()
        if target in seen:
            continue
        seen.add(target)
        change = changed_file_rated_by(changes, rating)
        if change is not None:
            yield rating, change


def changed_file_rated_by(
    changes: FileChanges, rating: FileRating
) -> FileChange | None:
    """The change `rating` is for, or `None` if it is stale or for an unchanged file."""
    target = rating.target()
    return next(
        (change for change in changes.root if RatingTarget.of_change(change) == target),
        None,
    )


def annotated_blob(change: FileChange, side: AnnotationSide) -> BlobSha | None:
    """The blob of `side` of the file, or `None` if the file has no such side."""
    version = change.before if side is AnnotationSide.BEFORE else change.after
    return None if version is None else version.blob
