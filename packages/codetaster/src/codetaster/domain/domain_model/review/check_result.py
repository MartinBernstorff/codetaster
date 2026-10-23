from pydantic import BaseModel, ConfigDict

from codetaster.domain.domain_model.review.adaptive_sampling import AdaptiveSampling
from codetaster.domain.domain_model.review.changes import (
    CommitSha,
    RevisionName,
    WorkingTreeState,
)
from codetaster.domain.domain_model.review.needs_review_threshold import (
    NeedsReviewThreshold,
)
from codetaster.domain.domain_model.review.ratings import PullRequestOverview
from codetaster.domain.domain_model.review.ratings_validation import (
    InvalidRatingsFile,
)
from codetaster.domain.domain_model.review.sampling import FileAssessments, Verdict


class CheckResult(BaseModel):
    """Which of the committed changes need human review."""

    model_config = ConfigDict(frozen=True)

    base: RevisionName
    merge_base: CommitSha
    head: CommitSha
    needs_review_threshold: NeedsReviewThreshold
    sampling: AdaptiveSampling
    """The base probability, and how the reviewer's evidence raised it."""
    assessments: FileAssessments
    working_tree: WorkingTreeState
    ratings_problem: InvalidRatingsFile | None
    """Why the ratings file was ignored, leaving every file unrated."""
    overview: PullRequestOverview | None
    """From the ratings file. `None` if it is missing or invalid."""

    @staticmethod
    def fake() -> CheckResult:
        return CheckResult(
            base=RevisionName.fake(),
            merge_base=CommitSha.fake(),
            head=CommitSha.fake(),
            needs_review_threshold=NeedsReviewThreshold.fake(),
            sampling=AdaptiveSampling.fake(),
            assessments=FileAssessments.fake(),
            working_tree=WorkingTreeState.CLEAN,
            ratings_problem=None,
            overview=PullRequestOverview.fake(),
        )

    def verdict(self) -> Verdict:
        """The most urgent group any file is in, or no-review without files."""
        present = {assessment.verdict for assessment in self.assessments.root}
        return next(
            (verdict for verdict in Verdict if verdict in present), Verdict.NO_REVIEW
        )

    def assessments_with(self, verdict: Verdict) -> FileAssessments:
        return FileAssessments(
            tuple(
                assessment
                for assessment in self.assessments.root
                if assessment.verdict is verdict
            )
        )
