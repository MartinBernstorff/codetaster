"""Hypothesis strategies and helpers for review models, shared by the tests."""

import json

from hypothesis import strategies as st

from codetaster.domain.domain_model.review.changes import (
    BlobSha,
    FileChange,
    FileVersion,
    RepositoryPath,
)
from codetaster.domain.domain_model.review.needs_review_threshold import (
    NeedsReviewThreshold,
)
from codetaster.domain.domain_model.review.probability import Probability
from codetaster.domain.domain_model.review.ratings import (
    CategoryDescription,
    DescribedCategory,
    FileRating,
    FileRatings,
    PullRequestSummary,
    RatingCategory,
    RatingsFile,
    RatingsFileContent,
    RatingTarget,
)
from codetaster.domain.domain_model.review.ratings_template import RatingsTemplate


def blob_shas() -> st.SearchStrategy[BlobSha]:
    return st.builds(BlobSha, st.from_regex(r"[0-9a-f]{40}", fullmatch=True))


def file_versions() -> st.SearchStrategy[FileVersion]:
    return st.builds(
        FileVersion,
        path=st.builds(
            RepositoryPath,
            st.from_regex(r"[a-z]{1,8}(/[a-z]{1,8})*\.py", fullmatch=True),
        ),
        blob=blob_shas(),
    )


def file_changes() -> st.SearchStrategy[FileChange]:
    return st.one_of(
        st.builds(FileChange, before=st.none(), after=file_versions()),
        st.builds(FileChange, before=file_versions(), after=st.none()),
        st.builds(FileChange, before=file_versions(), after=file_versions()),
    )


def distinct_file_changes() -> st.SearchStrategy[list[FileChange]]:
    """Changes to different files, as in one diff."""
    return st.lists(
        file_changes(), max_size=20, unique_by=lambda change: change.path().root
    )


def needs_review_thresholds() -> st.SearchStrategy[NeedsReviewThreshold]:
    return st.builds(NeedsReviewThreshold, st.floats(min_value=0, max_value=1))


def probabilities() -> st.SearchStrategy[Probability]:
    return st.builds(Probability, st.floats(min_value=0, max_value=1))


def ratings_of(change: FileChange) -> st.SearchStrategy[FileRating]:
    """Ratings whose path and blob match `change`."""
    target = RatingTarget.of_change(change)
    return st.builds(
        FileRating,
        path=st.just(target.path),
        blob=st.just(target.blob),
        probability=probabilities(),
        category=st.builds(RatingCategory, st.text(min_size=1)),
    )


def ratings_file_of(*ratings: FileRating) -> RatingsFile:
    """A ratings file that describes exactly the categories `ratings` use."""
    return RatingsFile(
        summary=PullRequestSummary.fake(),
        categories=tuple(
            DescribedCategory(name=category, description=CategoryDescription.fake())
            for category in dict.fromkeys(rating.category for rating in ratings)
        ),
        ratings=FileRatings(ratings),
    )


def fill_template(
    template: RatingsTemplate, ratings: list[FileRating]
) -> RatingsFileContent:
    """`template` filled in with `ratings`, one per entry, as an agent would."""
    filled = ratings_file_of(*ratings).model_dump(mode="json")
    filled["ratings"] = [
        entry.model_dump(mode="json")
        | {
            "probability": rating.probability.root,
            "category": rating.category.root,
            "annotations": [
                annotation.model_dump(mode="json") for annotation in rating.annotations
            ],
        }
        for entry, rating in zip(template.ratings, ratings, strict=True)
    ]
    return RatingsFileContent(json.dumps(filled))
