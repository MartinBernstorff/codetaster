import hashlib
import json
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, RootModel

from codetaster.domain.domain_model.review.changes import FileChange, FileChanges
from codetaster.domain.domain_model.review.path_rules import PathRule, PathRules
from codetaster.domain.domain_model.review.probability import Probability
from codetaster.domain.domain_model.review.ratings import FileRating, RatingsFile
from codetaster.domain.domain_model.review.top_rated import TopRatedPercentage


class Draw(RootModel[Annotated[float, Field(ge=0, lt=1)]]):
    """A file's reproducible random number. It is sampled if this is below the base probability."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> Draw:
        return Draw(0.5)


class Verdict(StrEnum):
    """The group a changed file is reported in, most urgent first.

    needs-review: among the top-rated files; see `assess_file_changes`.
    sampled: not needs-review, but the draw is below the base probability.
    no-review: everything else.
    """

    NEEDS_REVIEW = "needs-review"
    SAMPLED = "sampled"
    NO_REVIEW = "no-review"


def draw_for_file_change(change: FileChange) -> Draw:
    """SHA-256 over the before and after paths and blob SHAs, mapped to [0, 1).

    It depends only on the file's change, so it is the same on every machine,
    and new commits that leave the file's change alone do not re-draw it.
    """
    # [before_path, before_blob, after_path, after_blob], null for a missing side.
    fields = [
        value
        for version in (change.before, change.after)
        for value in (
            (None, None) if version is None else (version.path.root, version.blob.root)
        )
    ]
    digest = hashlib.sha256(json.dumps(fields).encode()).digest()
    # The top 53 bits, the precision of a float, so the result is never 1.0.
    top_bits = int.from_bytes(digest[:8], "big") >> 11
    return Draw(top_bits / 2**53)


class FileAssessment(BaseModel):
    """Which group a changed file is in, and what decided it.

    `base_probability` is the matching path rule's probability, or the configured
    base probability if `path_rule` is `None`. `rating` is `None` if the file is
    unrated.
    """

    model_config = ConfigDict(frozen=True)

    change: FileChange
    base_probability: Probability
    path_rule: PathRule | None
    rating: FileRating | None
    draw: Draw
    verdict: Verdict

    @staticmethod
    def fake() -> FileAssessment:
        return FileAssessment(
            change=FileChange.fake(),
            base_probability=Probability.fake(),
            path_rule=None,
            rating=None,
            draw=Draw.fake(),
            verdict=Verdict.NO_REVIEW,
        )


class FileAssessments(RootModel[tuple[FileAssessment, ...]]):
    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> FileAssessments:
        return FileAssessments((FileAssessment.fake(),))


def assess_file_changes(
    changes: FileChanges,
    base_probability: Probability,
    path_rules: PathRules,
    ratings: RatingsFile,
    top_rated: TopRatedPercentage,
) -> FileAssessments:
    """A matching path rule's probability replaces `base_probability` for sampling."""
    draws = tuple(draw_for_file_change(change) for change in changes.root)
    file_ratings = tuple(ratings.rating_for(change) for change in changes.root)
    file_rules = tuple(path_rules.rule_for(change.path()) for change in changes.root)
    file_base_probabilities = tuple(
        base_probability if rule is None else rule.probability for rule in file_rules
    )
    ranked = sorted(
        (
            (index, rating)
            for index, rating in enumerate(file_ratings)
            if rating is not None
        ),
        key=lambda rated: (-rated[1].probability.root, draws[rated[0]].root),
    )
    # The percentage of the changed files, rounded up.
    picked_count = -(-top_rated.root * len(changes.root) // 100)
    picked = {index for index, _ in ranked[:picked_count]}
    return FileAssessments(
        tuple(
            FileAssessment(
                change=change,
                base_probability=file_base,
                path_rule=rule,
                rating=rating,
                draw=draw,
                verdict=Verdict.NEEDS_REVIEW
                if index in picked
                else Verdict.SAMPLED
                if draw.root < file_base.root
                else Verdict.NO_REVIEW,
            )
            for index, (change, rule, file_base, rating, draw) in enumerate(
                zip(
                    changes.root,
                    file_rules,
                    file_base_probabilities,
                    file_ratings,
                    draws,
                    strict=True,
                )
            )
        )
    )
