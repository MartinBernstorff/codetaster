"""The `--format json` output of `codetaster check`."""

from typing import override

from pydantic import BaseModel, ConfigDict, Field, RootModel

from codetaster.domain.domain_model.review.adaptive_sampling import (
    AdaptiveSampling,
    BaseProbabilityWeight,
    CommentedFileCount,
    ViewedFileCount,
)
from codetaster.domain.domain_model.review.changes import (
    ChangeType,
    CommitSha,
    HunkStart,
    LineCount,
    LineSpan,
    RepositoryPath,
    RevisionName,
)
from codetaster.domain.domain_model.review.check_result import CheckResult
from codetaster.domain.domain_model.review.needs_review_threshold import (
    NeedsReviewThreshold,
)
from codetaster.domain.domain_model.review.path_rules import PathPattern, PathRule
from codetaster.domain.domain_model.review.probability import Probability
from codetaster.domain.domain_model.review.ratings import (
    AnnotationSide,
    AnnotationText,
    CategoryDescription,
    DescribedCategory,
    FileRating,
    LineAnnotation,
    LineNumber,
    PullRequestOverview,
    PullRequestSummary,
    RatedHunk,
    RatingCategory,
)
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
        return SchemaVersion(6)


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


class AnnotationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    side: AnnotationSide = Field(
        description="before or after: which version of the file `line` is in."
    )
    line: LineNumber = Field(
        description="The annotated line, counting from 1, in that version."
    )
    text: AnnotationText = Field(description="Markdown: the note for the reviewer.")

    @staticmethod
    def fake() -> AnnotationReport:
        return annotation_report_from_annotation(LineAnnotation.fake())


class LineSpanReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    start: HunkStart = Field(
        description="The first line, counting from 1. With a count of 0, the line "
        "before the gap, or 0 at the top of the file."
    )
    count: LineCount = Field(description="How many lines. 0 if there are none.")

    @staticmethod
    def fake() -> LineSpanReport:
        return line_span_report_from_span(LineSpan.fake())


class HunkReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    before: LineSpanReport | None = Field(
        description="The hunk's lines in the before version, as in a diff's hunk "
        "header. null if the hunk is for the whole change of a file without "
        "changed lines, e.g. a binary file."
    )
    after: LineSpanReport | None = Field(
        description="The hunk's lines in the after version. null when `before` is."
    )
    probability: Probability = Field(
        description="The AI's probability, from 0 to 1, that this hunk needs review."
    )

    @staticmethod
    def fake() -> HunkReport:
        return hunk_report_from_hunk(RatedHunk.fake())


class RatingReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    probability: Probability = Field(
        description="The AI's probability, from 0 to 1, that this file needs review: "
        "the highest of its hunks'."
    )
    category: RatingCategory = Field(
        description="Which part of the PR the AI put this file in.",
    )
    hunks: tuple[HunkReport, ...] = Field(
        description="Each run of changed lines and its AI rating, in order, as "
        "`git diff --unified=0` reports them."
    )
    annotations: tuple[AnnotationReport, ...] = Field(
        description="The AI's notes on lines of this version of the file, from the "
        "ratings file. Never posted as review comments."
    )

    @staticmethod
    def fake() -> RatingReport:
        return rating_report_from_rating(FileRating.fake())


class CategoryReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: RatingCategory = Field(description="As in each file's rating.category.")
    description: CategoryDescription = Field(
        description="Markdown: what the category's files change, and why."
    )

    @staticmethod
    def fake() -> CategoryReport:
        return category_report_from_category(DescribedCategory.fake())


class OverviewReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    summary: PullRequestSummary = Field(
        description="Markdown: what the PR does, referring to its categories by name."
    )
    categories: tuple[CategoryReport, ...] = Field(
        description="The categories the ratings file describes, in the order a "
        "reviewer should read them."
    )

    @staticmethod
    def fake() -> OverviewReport:
        return overview_report_from_overview(PullRequestOverview.fake())


class PathRuleReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    pattern: PathPattern = Field(description="The rule's glob.")
    probability: Probability = Field(
        description="The base probability for files matching `pattern`."
    )

    @staticmethod
    def fake() -> PathRuleReport:
        return path_rule_report_from_rule(PathRule.fake())


class SamplingReport(BaseModel):
    """How the reviewer's evidence raised the probability files are sampled at."""

    model_config = ConfigDict(frozen=True)

    base_probability: Probability = Field(
        description="[review] base_probability, before any evidence."
    )
    base_probability_weight: BaseProbabilityWeight = Field(
        description="[review] base_probability_weight: how many reviewed files "
        "base_probability counts as."
    )
    commented_files: CommentedFileCount = Field(
        description="--commented-files: sampled or needs-review files with a "
        "comment thread by the reviewer."
    )
    viewed_files: ViewedFileCount = Field(
        description="--viewed-files: sampled or needs-review files the reviewer "
        "viewed without commenting."
    )
    effective_probability: Probability = Field(
        description="The posterior mean of a Beta prior with mean base_probability "
        "worth base_probability_weight files, counting commented files as defects "
        "and viewed files as clean, but never below base_probability. "
        "base_probability without evidence."
    )

    @staticmethod
    def fake() -> SamplingReport:
        return sampling_report_from_sampling(AdaptiveSampling.fake())


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
    base_probability: Probability = Field(
        description="The probability the file is sampled at without evidence: "
        "path_rule's probability if a rule matches, else [review] base_probability."
    )
    sampling_probability: Probability = Field(
        description="The probability the file is sampled at: base_probability with "
        "its odds multiplied by those of sampling.effective_probability over those of "
        "sampling.base_probability. 0 and 1 stay as they are."
    )
    path_rule: PathRuleReport | None = Field(
        description="The last rule in [review] path_rules whose pattern matches "
        "`path`. null if none does."
    )
    rating: RatingReport | None = Field(
        description="The AI rating from [review] ratings_path whose path and blob "
        "match this file's change. null if the file is unrated."
    )
    unrated: ReportFlag = Field(
        description="true if no rating matches, so the file cannot be in needs-review."
    )
    draw: Draw = Field(
        description="From 0 inclusive to 1 exclusive. A file not in needs-review "
        "is sampled if draw < sampling_probability. SHA-256 over the JSON array [before_path, "
        "before_blob, after_path, after_blob], null for a missing side, with the "
        "first 53 bits divided by 2^53. It changes only when the file's change does."
    )

    @staticmethod
    def fake() -> FileReport:
        return file_report_from_assessment(FileAssessment.fake())


class CheckReport(BaseModel):
    """Which changed files need human review, in three groups. Every changed file
    is in exactly one group. Files are ordered by path.

    Each rating's `hunks` were added within version 6; its `probability` is the
    highest of theirs. Schema version 6 samples files at `sampling_probability`, which evidence from
    the reviewer raises above `base_probability`, and adds `sampling`. Version 5
    adds each rating's `annotations`. Version 4 picks needs-review by
    `needs_review_threshold`, replacing
    `top_rated_percentage`. Version 3 picked needs-review by rank, added
    `top_rated_percentage` and dropped each file's `probability`. In version 2, a file was in needs-review if
    its draw was below its rating. Schema version 2 added `sampled`. In version 1,
    `needs-review` held the files that are now `sampled`. The ratings file at [review] ratings_path is never
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
    needs_review_threshold: NeedsReviewThreshold = Field(
        description="The AI rating, from 0 to 1, at or above which a file needs "
        "review: --needs-review-threshold if given, else [review] "
        "needs_review_threshold."
    )
    sampling: SamplingReport
    ratings_error: RatingsErrorMessage | None = Field(
        description="Why the ratings file at [review] ratings_path was ignored, "
        "leaving every file unrated. null if it is valid or missing."
    )
    overview: OverviewReport | None = Field(
        description="The PR summary and category descriptions from the ratings "
        "file. null if it is missing or invalid."
    )
    needs_review_files: tuple[FileReport, ...] = Field(
        serialization_alias="needs-review",
        description="The rated files whose rating is at or above "
        "needs_review_threshold. Unrated files are never here.",
    )
    sampled_files: tuple[FileReport, ...] = Field(
        serialization_alias="sampled",
        description="The files not in needs-review that were picked at random, at "
        "sampling_probability, for human review.",
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
        schema_version=SchemaVersion(6),
        needs_review=ReportFlag(root=result.verdict() is not Verdict.NO_REVIEW),
        # Nothing applies an override label yet.
        override_label_applied=ReportFlag(root=False),
        base=BaseReport(ref=result.base, merge_base=result.merge_base),
        head=HeadReport(commit=result.head),
        needs_review_threshold=result.needs_review_threshold,
        sampling=sampling_report_from_sampling(result.sampling),
        ratings_error=None
        if result.ratings_problem is None
        else ratings_error_message(result.ratings_problem),
        overview=None
        if result.overview is None
        else overview_report_from_overview(result.overview),
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
        sampling_probability=assessment.sampling_probability,
        path_rule=None
        if assessment.path_rule is None
        else path_rule_report_from_rule(assessment.path_rule),
        rating=None
        if assessment.rating is None
        else rating_report_from_rating(assessment.rating),
        unrated=ReportFlag(root=assessment.rating is None),
        draw=assessment.draw,
    )


def sampling_report_from_sampling(sampling: AdaptiveSampling) -> SamplingReport:
    return SamplingReport(
        base_probability=sampling.base_probability,
        base_probability_weight=sampling.weight,
        commented_files=sampling.evidence.commented_files,
        viewed_files=sampling.evidence.viewed_files,
        effective_probability=sampling.effective_probability(),
    )


def path_rule_report_from_rule(rule: PathRule) -> PathRuleReport:
    return PathRuleReport(pattern=rule.pattern, probability=rule.probability)


def rating_report_from_rating(rating: FileRating) -> RatingReport:
    return RatingReport(
        probability=rating.probability(),
        category=rating.category,
        hunks=tuple(hunk_report_from_hunk(hunk) for hunk in rating.hunks),
        annotations=tuple(
            annotation_report_from_annotation(annotation)
            for annotation in rating.annotations
        ),
    )


def hunk_report_from_hunk(hunk: RatedHunk) -> HunkReport:
    return HunkReport(
        before=None if hunk.before is None else line_span_report_from_span(hunk.before),
        after=None if hunk.after is None else line_span_report_from_span(hunk.after),
        probability=hunk.probability,
    )


def line_span_report_from_span(span: LineSpan) -> LineSpanReport:
    return LineSpanReport(start=span.start, count=span.count)


def annotation_report_from_annotation(annotation: LineAnnotation) -> AnnotationReport:
    return AnnotationReport(
        side=annotation.side, line=annotation.line, text=annotation.text
    )


def overview_report_from_overview(overview: PullRequestOverview) -> OverviewReport:
    return OverviewReport(
        summary=overview.summary,
        categories=tuple(
            category_report_from_category(category) for category in overview.categories
        ),
    )


def category_report_from_category(category: DescribedCategory) -> CategoryReport:
    return CategoryReport(name=category.name, description=category.description)
