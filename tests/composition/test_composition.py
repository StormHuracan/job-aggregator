from unittest.mock import MagicMock, patch

from job_aggregator.composition import build_collection_service


def test_build_collection_service():
    user_id = 1
    session = MagicMock()
    session_factory = MagicMock()
    settings = MagicMock()

    with (
        patch("job_aggregator.composition.VacancyRepository") as repository_mock,
        patch("job_aggregator.composition.AuthorizedHHAPIClient") as authorized_mock,
        patch("job_aggregator.composition.HHClient") as hh_client_mock,
        patch("job_aggregator.composition.VacancyCollectionService") as service_mock,
    ):
        repository = repository_mock.return_value
        authorized_client = authorized_mock.return_value
        hh_client = hh_client_mock.return_value

        service = build_collection_service(
            user_id=user_id,
            session=session,
            session_factory=session_factory,
            settings=settings,
        )

    repository_mock.assert_called_once_with(session=session)

    authorized_mock.assert_called_once_with(
        session_factory=session_factory,
        user_id=user_id,
        allow_token_refresh=settings.hh_allow_token_refresh,
        client_id=settings.hh_client_id,
        client_secret=settings.hh_client_secret,
    )

    hh_client_mock.assert_called_once_with(authorized_client)

    service_mock.assert_called_once_with(
        client=hh_client,
        repository=repository,
    )

    assert service is service_mock.return_value
