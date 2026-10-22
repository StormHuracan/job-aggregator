from urllib.parse import unquote

from job_aggregator.api.dependencies import get_auth_session_service, get_db_session
from job_aggregator.core.config import Settings, get_settings


def test_login(app, client) -> None:
    def fake_login():
        return Settings(hh_client_id=None, hh_client_secret=None, _env_file=None)

    ser_pass = FakeService()

    def get_ser_pass():
        return ser_pass

    app.dependency_overrides[get_auth_session_service] = get_ser_pass
    app.dependency_overrides[get_settings]= fake_login
    response = client.get("/auth/hh/login")
    assert response.status_code == 503
    assert response.json() == {"detail": "Авторизация временно недоступна"}
    assert ser_pass.calls == 0

class FakeService:
    def __init__(self):
        self.met = ["Метка", "Метка_2"]
        self.calls = 0

    async def create_oauth_state(self):
        self.calls += 1
        return self.met.pop(0)





class FakeSession:
    async def commit(self):
        pass

def test_login_redirect(app, client) -> None:
    def fake_setting():
        return Settings(
            hh_client_id="test-client",
            hh_client_secret="test-secret",
            hh_redirect_uri="https://example",
            _env_file=None,
        )

    ser_pass = FakeService()

    def get_ser_pass():
        return ser_pass

    app.dependency_overrides[get_auth_session_service] = get_ser_pass
    app.dependency_overrides[get_db_session] = FakeSession
    app.dependency_overrides[get_settings] = fake_setting

    response = client.get("/auth/hh/login", follow_redirects=False)
    response_2 = client.get("/auth/hh/login", follow_redirects=False)
    assert response.status_code == 307
    assert response_2.status_code == 307
    res = unquote(response.headers["location"])
    res_2 = unquote(response_2.headers["location"])
    assert "state=Метка" in res
    assert "state=Метка_2" in res_2
    assert ser_pass.calls == 2

def test_login_without_redirect_url_returns_503(app, client) -> None:
    def fake_setting():
        return Settings(
            hh_client_id="test-client",
            hh_client_secret="test-secret",
            hh_redirect_uri=None,
            _env_file=None,
        )

    ser_pass = FakeService()

    def get_ser_pass():
        return ser_pass

    app.dependency_overrides[get_auth_session_service] = get_ser_pass
    app.dependency_overrides[get_db_session] = FakeSession
    app.dependency_overrides[get_settings] = fake_setting

    response = client.get("/auth/hh/login", follow_redirects=False)

    assert ser_pass.calls == 0
    assert response.status_code == 503
    assert response.json() == {"detail": "Авторизация временно недоступна"}
