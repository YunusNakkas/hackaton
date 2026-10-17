from tests.conftest import CSRF, PASSWORD, assert_contract


def test_login_sets_httponly_cookie_and_returns_me(anon_client):
    res = anon_client.post("/api/v1/auth/login", json={"email": "Elif@Demo.Test", "password": PASSWORD}, headers=CSRF)
    assert res.status_code == 200
    assert_contract("Me", res.json())
    assert res.json()["user"]["role"] == "employee"
    cookie = res.headers["set-cookie"]
    assert "pm_session=" in cookie and "HttpOnly" in cookie and "samesite=lax" in cookie.lower()

    me = anon_client.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "elif@demo.test"


def test_wrong_password_is_401_with_contract_error(anon_client):
    res = anon_client.post("/api/v1/auth/login", json={"email": "elif@demo.test", "password": "yanlis"}, headers=CSRF)
    assert res.status_code == 401
    assert_contract("Error", res.json())
    assert res.json()["error"]["code"] == "invalid_credentials"
    assert res.headers["x-request-id"] == res.json()["error"]["request_id"]


def test_unknown_email_gives_same_error(anon_client):
    res = anon_client.post("/api/v1/auth/login", json={"email": "yok@demo.test", "password": "x"}, headers=CSRF)
    assert res.status_code == 401 and res.json()["error"]["code"] == "invalid_credentials"


def test_login_rate_limited_after_five_failures(anon_client):
    for _ in range(5):
        anon_client.post("/api/v1/auth/login", json={"email": "elif@demo.test", "password": "x"}, headers=CSRF)
    res = anon_client.post("/api/v1/auth/login", json={"email": "elif@demo.test", "password": PASSWORD}, headers=CSRF)
    assert res.status_code == 429 and res.json()["error"]["code"] == "rate_limited"


def test_mutation_without_csrf_header_is_rejected(anon_client):
    res = anon_client.post("/api/v1/auth/login", json={"email": "elif@demo.test", "password": PASSWORD})
    assert res.status_code == 403
    assert_contract("Error", res.json())
    assert res.json()["error"]["code"] == "csrf_header_missing"


def test_me_requires_login(anon_client):
    res = anon_client.get("/api/v1/me")
    assert res.status_code == 401
    assert_contract("Error", res.json())


def test_logout_invalidates_session(elif_client):
    assert elif_client.post("/api/v1/auth/logout", headers=CSRF).status_code == 204
    assert elif_client.get("/api/v1/me").status_code == 401


def test_validation_error_has_field_details(anon_client):
    res = anon_client.post("/api/v1/auth/login", json={"email": "gecersiz"}, headers=CSRF)
    assert res.status_code == 422
    assert_contract("Error", res.json())
    fields = res.json()["error"]["details"]["fields"]
    assert "email" in fields and "password" in fields
