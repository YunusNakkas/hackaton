from fastapi.testclient import TestClient

from app.main import app


def test_health_matches_contract_shape():
    res = TestClient(app).get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] in {"ok", "degraded"}
    assert body["model_service"] in {"up", "down", "stub"}
