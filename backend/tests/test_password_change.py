import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import CSRF, PASSWORD, assert_contract

TEMP = "temporary-test-123"
NEW = "personal-test-456"


def temporary_client(manager):
    created = manager.post("/api/v1/admin/employees", headers=CSRF, json={
        "email": "password-flow@demo.test", "display_name": "Şifre Testi", "temporary_password": TEMP,
    })
    assert created.status_code == 201
    client = TestClient(create_app())
    login = client.post("/api/v1/auth/login", headers=CSRF, json={"email": "password-flow@demo.test", "password": TEMP})
    assert login.status_code == 200 and login.json()["user"]["must_change_password"]
    return client


def change(client, **values):
    return client.post("/api/v1/auth/change-password", headers=CSRF, json={
        "current_password": TEMP, "new_password": NEW, "confirm_password": NEW, **values,
    })


def test_temporary_password_requires_change_rotates_sessions_and_is_single_use(manager_client):
    client = temporary_client(manager_client)
    other = TestClient(create_app())
    other.post("/api/v1/auth/login", headers=CSRF, json={"email": "password-flow@demo.test", "password": TEMP})
    old_cookie = client.cookies.get("pm_session")
    denied = client.get("/api/v1/trainings")
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "password_change_required"
    assert client.get("/api/v1/me").status_code == 200
    training = manager_client.get("/api/v1/trainings").json()["items"][0]
    assert client.post("/api/v1/sessions", headers=CSRF, json={
        "training_id": training["id"], "client_request_id": "a2bbd7a2-7b1d-46de-839e-36ba821c21ca",
    }).status_code == 403
    result = change(client)
    assert result.status_code == 200, result.text
    assert_contract("Me", result.json())
    assert not result.json()["user"]["must_change_password"]
    assert "HttpOnly" in result.headers["set-cookie"]
    assert client.cookies.get("pm_session") != old_cookie
    assert client.get("/api/v1/trainings").status_code == 200
    assert other.get("/api/v1/me").status_code == 401
    assert manager_client.get("/api/v1/admin/overview").status_code == 200
    fresh = TestClient(create_app())
    assert fresh.post("/api/v1/auth/login", headers=CSRF, json={"email": "password-flow@demo.test", "password": TEMP}).status_code == 401
    assert fresh.post("/api/v1/auth/login", headers=CSRF, json={"email": "password-flow@demo.test", "password": NEW}).status_code == 200


@pytest.mark.parametrize("values,status", [
    ({"current_password": "wrong"}, 400),
    ({"confirm_password": "mismatch-123"}, 422),
    ({"new_password": TEMP, "confirm_password": TEMP}, 422),
    ({"new_password": "short", "confirm_password": "short"}, 422),
    ({"new_password": "        ", "confirm_password": "        "}, 422),
    ({"user_id": "another-user"}, 422),
])
def test_invalid_changes_do_not_change_password_or_unlock_account(manager_client, values, status):
    client = temporary_client(manager_client)
    response = change(client, **values)
    assert response.status_code == status, response.text
    assert_contract("Error", response.json())
    assert client.get("/api/v1/me").json()["user"]["must_change_password"]
    assert client.get("/api/v1/trainings").status_code == 403
    assert change(client).status_code == 200


def test_password_change_rate_limit(manager_client):
    client = temporary_client(manager_client)
    for _ in range(5):
        assert change(client, current_password="wrong").status_code == 400
    assert change(client).status_code == 429


def test_change_requires_authentication_and_csrf(anon_client, elif_client):
    assert change(anon_client).status_code == 401
    assert elif_client.post("/api/v1/auth/change-password", json={
        "current_password": PASSWORD, "new_password": NEW, "confirm_password": NEW,
    }).status_code == 403


def test_existing_user_can_change_current_password(elif_client):
    assert not elif_client.get("/api/v1/me").json()["user"]["must_change_password"]
    result = change(elif_client, current_password=PASSWORD)
    assert result.status_code == 200
    assert elif_client.get("/api/v1/trainings").status_code == 200


def test_deactivated_employee_cannot_change_password(manager_client):
    client = temporary_client(manager_client)
    uid = client.get("/api/v1/me").json()["user"]["id"]
    manager_client.post(f"/api/v1/admin/employees/{uid}/deactivate", headers=CSRF)
    assert change(client).status_code == 401
