import hashlib
import json
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, RootModel

from codetaster.domain.domain_model.review.changes import FileChange


class Probability(RootModel[Annotated[float, Field(ge=0, le=1)]]):
    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> Probability:
        return Probability(0.5)


class Draw(RootModel[Annotated[float, Field(ge=0, lt=1)]]):
    """A file's reproducible random number. It needs review if this is below its probability."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> Draw:
        return Draw(0.5)


class Verdict(StrEnum):
    """The group a changed file is reported in, most urgent first.

    needs-review: the draw is below the file's rating.
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
    """Which group a changed file is in, and what decided it."""

    model_config = ConfigDict(frozen=True)

    change: FileChange
    base_probability: Probability
    probability: Probability
    draw: Draw
    verdict: Verdict

    @staticmethod
    def fake() -> FileAssessment:
        return FileAssessment(
            change=FileChange.fake(),
            base_probability=Probability.fake(),
            probability=Probability.fake(),
            draw=Draw.fake(),
            verdict=Verdict.NO_REVIEW,
        )


class FileAssessments(RootModel[tuple[FileAssessment, ...]]):
    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> FileAssessments:
        return FileAssessments((FileAssessment.fake(),))


def assess_file_change(
    change: FileChange, base_probability: Probability
) -> FileAssessment:
    """Without a rating a file can only be sampled, never needs-review."""
    draw = draw_for_file_change(change)
    return FileAssessment(
        change=change,
        base_probability=base_probability,
        probability=base_probability,
        draw=draw,
        verdict=Verdict.SAMPLED
        if draw.root < base_probability.root
        else Verdict.NO_REVIEW,
    )
