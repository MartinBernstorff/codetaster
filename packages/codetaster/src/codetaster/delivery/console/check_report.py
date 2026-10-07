"""The `--format json` output of `codetaster check`."""

from typing import override

from pydantic import BaseModel, ConfigDict, Field, RootModel

from codetaster.domain.domain_model.review.changes import (
    ChangeType,
    CommitSha,
    RepositoryPath,
    RevisionName,
)
from codetaster.domain.domain_model.review.check_result import CheckResult
from codetaster.domain.domain_model.review.probability import Probability
from codetaster.domain.domain_model.review.ratings import FileRating, RatingReason
from codetaster.domain.domain_model.review.ratings_validation import (
    InvalidRatingsFile,
)
from codetaster.domain.domain_model.review.sampling import (
    Draw,
    FileAssessment,
    Verdict,
)


class SchemaVersion(RootModel[int]):
    """Bumped when a field is removed or changes meaning. Adding a field keeps it."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> SchemaVersion:
        return SchemaVersion(2)


class ReportFlag(RootModel[bool]):
    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> ReportFlag:
        return ReportFlag(root=False)


class RatingsErrorMessage(RootModel[str]):
    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return self.root

    @staticmethod
    def fake() -> RatingsErrorMessage:
        return ratings_error_message(InvalidRatingsFile.fake())


class BaseReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    ref: RevisionName = Field(
        description="The base branch: --base if given, else [review] base_branch."
    )
    merge_base: CommitSha = Field(
        description="The merge base of `ref` and HEAD. The change is merge_base..head."
    )

    @staticmethod
    def fake() -> BaseReport:
        return BaseReport(ref=RevisionName.fake(), merge_base=CommitSha.fake())


class HeadReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    commit: CommitSha = Field(description="HEAD. Uncommitted changes are not included.")

    @staticmethod
    def fake() -> HeadReport:
        return HeadReport(commit=CommitSha.fake())


class RatingReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    probability: Probability = Field(
        description="The AI's probability, from 0 to 1, that this file needs review."
    )
    reason: RatingReason = Field(description="The AI's one-sentence reason.")

    @staticmethod
    def fake() -> RatingReport:
        return rating_report_from_rating(FileRating.fake())


class FileReport(BaseModel):
    """One changed file, and the inputs to whether it needs review."""

    model_config = ConfigDict(frozen=True)

    path: RepositoryPath = Field(
        description="From the repository root, with / separators. A renamed file's "
        "new path, a deleted file's old path."
    )
    previous_path: RepositoryPath | None = Field(
        description="A renamed file's old path. null for other change types."
    )
    change_type: ChangeType = Field(description="added, modified, deleted or renamed.")
    base_probability: Probability = Field(description="[review] base_probability.")
    rating: RatingReport | None = Field(
        description="The AI rating from [review] ratings_path whose path and blob "
        "match this file's change. null if the file is unrated."
    )
    unrated: ReportFlag = Field(
        description="true if no rating matches, so only base_probability applies."
    )
    probability: Probability = Field(
        description="The probability, from 0 to 1, that this file needs review: "
        "the larger of base_probability and the rating's probability."
    )
    draw: Draw = Field(
        description="From 0 inclusive to 1 exclusive. The file is in needs-review "
        "if draw < the rating's probability, else sampled if draw < "
        "base_probability. SHA-256 over the JSON array [before_path, "
        "before_blob, after_path, after_blob], null for a missing side, with the "
        "first 53 bits divided by 2^53. It changes only when the file's change does."
    )

    @staticmethod
    def fake() -> FileReport:
        return file_report_from_assessment(FileAssessment.fake())


class CheckReport(BaseModel):
    """Which changed files need human review, in three groups. Every changed file
    is in exactly one group. Files are ordered by path.

    Schema version 2 added `sampled`. In version 1, `needs-review` held the files
    that are now `sampled`. The ratings file at [review] ratings_path is never
    listed.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: SchemaVersion = Field(
        description="Bumped when a field is removed or changes meaning. New fields "
        "can appear without a bump, so ignore fields you don't know."
    )
    needs_review: ReportFlag = Field(
        description="true if any file is in needs-review or sampled."
    )
    override_label_applied: ReportFlag = Field(
        description="true if a PR label forced every file into needs-review. "
        "Always false for now."
    )
    base: BaseReport
    head: HeadReport
    ratings_error: RatingsErrorMessage | None = Field(
        description="Why the ratings file at [review] ratings_path was ignored, "
        "leaving every file unrated. null if it is valid or missing."
    )
    needs_review_files: tuple[FileReport, ...] = Field(
        serialization_alias="needs-review",
        description="The files whose draw is below their rating's probability. "
        "Unrated files are never here.",
    )
    sampled_files: tuple[FileReport, ...] = Field(
        serialization_alias="sampled",
        description="The files not in needs-review that were picked at random, at "
        "base_probability, for human review.",
    )
    no_review_files: tuple[FileReport, ...] = Field(
        serialization_alias="no-review",
        description="The files that need no human review.",
    )

    @staticmethod
    def fake() -> CheckReport:
        return check_report_from_result(CheckResult.fake())


def check_report_from_result(result: CheckResult) -> CheckReport:
    def files_with(verdict: Verdict) -> tuple[FileReport, ...]:
        return tuple(
            file_report_from_assessment(assessment)
            for assessment in result.assessments_with(verdict).root
        )

    return CheckReport(
        schema_version=SchemaVersion(2),
        needs_review=ReportFlag(root=result.verdict() is not Verdict.NO_REVIEW),
        # Nothing applies an override label yet.
        override_label_applied=ReportFlag(root=False),
        base=BaseReport(ref=result.base, merge_base=result.merge_base),
        head=HeadReport(commit=result.head),
        ratings_error=None
        if result.ratings_problem is None
        else ratings_error_message(result.ratings_problem),
        needs_review_files=files_with(Verdict.NEEDS_REVIEW),
        sampled_files=files_with(Verdict.SAMPLED),
        no_review_files=files_with(Verdict.NO_REVIEW),
    )


def ratings_error_message(problem: InvalidRatingsFile) -> RatingsErrorMessage:
    return RatingsErrorMessage(
        f"invalid ratings file {problem.location.root}: {problem.reason.root}"
    )


def file_report_from_assessment(assessment: FileAssessment) -> FileReport:
    return FileReport(
        path=assessment.change.path(),
        previous_path=assessment.change.previous_path(),
        change_type=assessment.change.change_type(),
        base_probability=assessment.base_probability,
        rating=None
        if assessment.rating is None
        else rating_report_from_rating(assessment.rating),
        unrated=ReportFlag(root=assessment.rating is None),
        probability=assessment.probability,
        draw=assessment.draw,
    )


def rating_report_from_rating(rating: FileRating) -> RatingReport:
    return RatingReport(probability=rating.probability, reason=rating.reason)
