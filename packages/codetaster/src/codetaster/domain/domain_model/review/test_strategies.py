"""Hypothesis strategies for review models, shared by the tests in this folder."""

from hypothesis import strategies as st

from codetaster.domain.domain_model.review.changes import (
    BlobSha,
    FileChange,
    FileVersion,
    RepositoryPath,
)
from codetaster.domain.domain_model.review.probability import Probability
from codetaster.domain.domain_model.review.ratings import (
    FileRating,
    RatingReason,
    RatingTarget,
)


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
        reason=st.builds(RatingReason, st.text(min_size=1)),
    )
