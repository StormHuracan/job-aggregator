from typing import Annotated
from unittest.mock import Mock

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient


@pytest.mark.parametrize("value", ["first", "second"])
def test_client_isolates_dependency_overrides(client: TestClient, value: str) -> None:
    assert client.app.dependency_overrides == {}
    assert client.get("/test-dependency").status_code == 404

    def get_value() -> str:
        raise AssertionError("Должна вызываться подмена зависимости")

    @client.app.get("/test-dependency")
    def read_value(value: Annotated[str, Depends(get_value)]) -> dict[str, str]:
        return {"value": value}

    override = Mock(return_value=value)
    client.app.dependency_overrides[get_value] = lambda: override()

    response = client.get("/test-dependency")

    assert response.status_code == 200
    assert response.json() == {"value": value}
    override.assert_called_once_with()


@pytest.fixture
def forbid_production_database(monkeypatch: pytest.MonkeyPatch) -> Mock:
    create_engine = Mock(side_effect=AssertionError("API-тест не должен создавать БД"))
    monkeypatch.setattr("job_aggregator.main.create_engine_and_factory", create_engine)
    return create_engine


def test_client_uses_real_routes_without_production_lifespan(
    forbid_production_database: Mock, client: TestClient
) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    forbid_production_database.assert_not_called()
