"""The `--format json` output of `codetaster check`."""

from pydantic import BaseModel, ConfigDict, Field, RootModel

from codetaster.domain.domain_model.review.changes import (
    ChangeType,
    CommitSha,
    RepositoryPath,
    RevisionName,
)
from codetaster.domain.domain_model.review.check_result import CheckResult
from codetaster.domain.domain_model.review.sampling import (
    Draw,
    FileAssessment,
    Probability,
    Verdict,
)


class SchemaVersion(RootModel[int]):
    """Bumped when a field is removed or changes meaning. Adding a field keeps it."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> SchemaVersion:
        return SchemaVersion(1)


class ReportFlag(RootModel[bool]):
    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> ReportFlag:
        return ReportFlag(root=False)


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
    probability: Probability = Field(
        description="The probability, from 0 to 1, that this file needs review."
    )
    draw: Draw = Field(
        description="From 0 inclusive to 1 exclusive. The file needs review if "
        "draw < probability. SHA-256 over the JSON array [before_path, "
        "before_blob, after_path, after_blob], null for a missing side, with the "
        "first 53 bits divided by 2^53. It changes only when the file's change does."
    )

    @staticmethod
    def fake() -> FileReport:
        return file_report_from_assessment(FileAssessment.fake())


class CheckReport(BaseModel):
    """Which changed files need human review. Files are ordered by path."""

    model_config = ConfigDict(frozen=True)

    schema_version: SchemaVersion = Field(
        description="Bumped when a field is removed or changes meaning. New fields "
        "can appear without a bump, so ignore fields you don't know."
    )
    needs_review: ReportFlag = Field(description="true if any file is in needs-review.")
    override_label_applied: ReportFlag = Field(
        description="true if a PR label forced every file into needs-review. "
        "Always false for now."
    )
    base: BaseReport
    head: HeadReport
    needs_review_files: tuple[FileReport, ...] = Field(
        serialization_alias="needs-review",
        description="The files that need human review.",
    )
    no_review_files: tuple[FileReport, ...] = Field(
        serialization_alias="no-review", description="The files that don't."
    )

    @staticmethod
    def fake() -> CheckReport:
        return check_report_from_result(CheckResult.fake())


def check_report_from_result(result: CheckResult) -> CheckReport:
    def files_with(verdict: Verdict) -> tuple[FileReport, ...]:
        return tuple(
            file_report_from_assessment(assessment)
            for assessment in result.assessments.root
            if assessment.verdict is verdict
        )

    return CheckReport(
        schema_version=SchemaVersion(1),
        needs_review=ReportFlag(root=result.verdict() is Verdict.NEEDS_REVIEW),
        # Nothing applies an override label yet.
        override_label_applied=ReportFlag(root=False),
        base=BaseReport(ref=result.base, merge_base=result.merge_base),
        head=HeadReport(commit=result.head),
        needs_review_files=files_with(Verdict.NEEDS_REVIEW),
        no_review_files=files_with(Verdict.NO_REVIEW),
    )


def file_report_from_assessment(assessment: FileAssessment) -> FileReport:
    return FileReport(
        path=assessment.change.path(),
        previous_path=assessment.change.previous_path(),
        change_type=assessment.change.change_type(),
        base_probability=assessment.base_probability,
        probability=assessment.probability,
        draw=assessment.draw,
    )
