from hh_applicant_tool.api import ApiClient, OAuthClient


def test_hh_applicant_tool_public_clients_are_available() -> None:
    oauth_client = OAuthClient()

    assert callable(ApiClient.request)
    assert callable(ApiClient.get)
    assert isinstance(oauth_client.authorize_url, str)
    assert callable(OAuthClient.request_access_token)
