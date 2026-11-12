from safe_result import Err, Ok

from codetaster.domain.application_services.write_ratings_template import (
    RatingsTemplateWriteRequest,
    RatingsTemplateWriteResult,
    write_ratings_template,
)
from codetaster.domain.domain_model.configuration.configuration import Configuration
from codetaster.domain.domain_model.filesystem import ExistingFilePolicy, Location
from codetaster.domain.domain_model.review.changes import (
    BlobSha,
    RepositoryPath,
    RevisionName,
)
from codetaster.domain.domain_model.review.ratings import (
    RatingsFile,
    RatingsFileContent,
    RatingsFileExistsError,
    ratings_file_location,
)
from codetaster.domain.domain_model.review.ratings_template import RatingsTemplate

# Domain tests use the fakes from infrastructure, which tach otherwise forbids.
from codetaster.infrastructure.committed_changes.fake_committed_changes import (
    FakeCommittedChanges,
)
from codetaster.infrastructure.ratings_file_store.in_memory import (
    InMemoryRatingsFileStore,
)


def history_with_feature_branch(
    base: RevisionName, *feature_files: RepositoryPath
) -> FakeCommittedChanges:
    """`base` has one commit; the checked-out `feature` branch adds `feature_files`."""
    history = FakeCommittedChanges(base)
    _ = history.commit({RepositoryPath("README.md"): BlobSha.fake()})
    history.create_branch(RevisionName("feature"))
    _ = history.commit({path: BlobSha.fake() for path in feature_files})
    return history


def configured_location(configuration: Configuration) -> Location:
    assert configuration.review is not None
    return ratings_file_location(
        RatingsTemplateWriteRequest.fake().checkout, configuration.review.ratings_path
    )


def written_template(
    configuration: Configuration,
    history: FakeCommittedChanges,
    store: InMemoryRatingsFileStore,
    request: RatingsTemplateWriteRequest | None = None,
) -> RatingsTemplateWriteResult:
    match write_ratings_template(
        request or RatingsTemplateWriteRequest.fake(), configuration, history, store
    ):
        case Ok(result):
            return result
        case Err(error):
            raise error


def stored_template(
    store: InMemoryRatingsFileStore, location: Location
) -> RatingsTemplate:
    return RatingsTemplate.model_validate_json(store.files[location].root)


def test_writes_the_template_to_the_configured_ratings_path() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    path = RepositoryPath.fake()
    history = history_with_feature_branch(configuration.review.base_branch, path)
    store = InMemoryRatingsFileStore({})
    location = configured_location(configuration)

    result = written_template(configuration, history, store)

    assert result.location == location
    assert [entry.path for entry in stored_template(store, location).ratings] == [path]


def test_refuses_to_replace_an_existing_ratings_file() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    history = history_with_feature_branch(
        configuration.review.base_branch, RepositoryPath.fake()
    )
    location = configured_location(configuration)
    existing = RatingsFileContent(RatingsFile.fake().model_dump_json())
    store = InMemoryRatingsFileStore({location: existing})

    result = write_ratings_template(
        RatingsTemplateWriteRequest.fake(), configuration, history, store
    )

    match result:
        case Err(RatingsFileExistsError() as error):
            assert error.location == location
        case _:
            raise AssertionError(result)
    assert store.files[location] == existing


def test_overwrite_replaces_an_existing_ratings_file() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    path = RepositoryPath.fake()
    history = history_with_feature_branch(configuration.review.base_branch, path)
    location = configured_location(configuration)
    store = InMemoryRatingsFileStore(
        {location: RatingsFileContent(RatingsFile.fake().model_dump_json())}
    )
    request = RatingsTemplateWriteRequest.fake().model_copy(
        update={"existing_file": ExistingFilePolicy.OVERWRITE}
    )

    _ = written_template(configuration, history, store, request)

    assert [entry.path for entry in stored_template(store, location).ratings] == [path]


def test_writes_nothing_when_the_change_cannot_be_read() -> None:
    configuration = Configuration.fake()
    request = RatingsTemplateWriteRequest.fake().model_copy(
        update={"base_override": RevisionName("no-such-branch")}
    )
    history = history_with_feature_branch(RevisionName.fake(), RepositoryPath.fake())
    store = InMemoryRatingsFileStore({})

    result = write_ratings_template(request, configuration, history, store)

    assert isinstance(result, Err)
    assert store.files == {}
