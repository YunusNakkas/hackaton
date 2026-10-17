import json

import pytest

from app.services.model_client import StubModelClient
from app.worker.jobs import run_once
from tests.conftest import CSRF, PASSWORD, _client, assert_contract
from tests.test_session_flow import _start, _upload

FORM = {
    "business_name": "Kahve Durağı", "sector": "cafe", "language": "tr",
    "policies": [{"title": "İade", "body": "Yanlış hazırlanan içecek ücretsiz yeniden yapılır."},
                 {"title": "Sadakat", "body": "10 kahvede 1 kahve bedava."}],
    "customer_situations": ["Siparişi yanlış hazırlanan müşteri", "Kampanyayı soran müşteri"],
    "must_do": ["Özür dile"], "must_not_do": ["Para iadesi vaat etme"],
    "escalation_rule": None, "scenario_count": 2,
}


class UnverifiableEvaluator(StubModelClient):
    """Transkriptte olmayan alıntı üretir → rapor needs_review olmalı."""

    def chat(self, messages, **kw):
        if kw["purpose"] == "evaluation":
            dims = kw["stub_context"]["dimension_ids"]
            return json.dumps({"dimensions": [
                {"dimension_id": d, "score": 3, "rationale": "r",
                 "evidence": [{"turn_id": "t1", "quote": "hiç söylenmemiş bir cümle"}], "policy_refs": []}
                for d in dims], "strengths": [], "improvements": []})
        return super().chat(messages, **kw)


def _finished_session(client, model=None) -> str:
    sid = _start(client)["session"]["id"]
    _upload(client, sid)
    assert run_once(model=model)
    assert client.post(f"/api/v1/sessions/{sid}/finish", headers=CSRF).status_code == 202
    assert run_once(model=model)
    return sid


@pytest.mark.parametrize("method,path", [
    ("get", "/api/v1/admin/overview"), ("get", "/api/v1/admin/employees"), ("get", "/api/v1/admin/sessions"),
    ("post", "/api/v1/admin/assignments"), ("get", "/api/v1/admin/training-drafts"),
])
def test_employee_cannot_use_admin(elif_client, method, path):
    res = getattr(elif_client, method)(path, headers=CSRF, **({"json": {}} if method == "post" else {}))
    assert res.status_code == 403
    assert_contract("Error", res.json())


def test_overview_counts(manager_client):
    res = manager_client.get("/api/v1/admin/overview").json()
    assert_contract("AdminOverview", res)
    assert res == {"active_employees": 2, "open_assignments": 1, "completed_assignments": 0,
                   "sessions_pending_review": 0, "sessions_last_7_days": 0}


def test_employee_lifecycle(manager_client, env):
    page = manager_client.get("/api/v1/admin/employees").json()
    assert_contract("EmployeePage", page)
    assert {e["email"] for e in page["items"]} == {"elif@demo.test", "can@demo.test"}  # yönetici listede yok
    assert len(manager_client.get("/api/v1/admin/employees", params={"q": "ELİF"}).json()["items"]) <= 1
    assert [e["email"] for e in manager_client.get("/api/v1/admin/employees", params={"q": "can"}).json()["items"]] \
        == ["can@demo.test"]

    body = {"email": "Yeni@Demo.Test", "display_name": "Yeni Çalışan", "temporary_password": "gecici-123"}
    created = manager_client.post("/api/v1/admin/employees", headers=CSRF, json=body)
    assert created.status_code == 201
    assert_contract("Employee", created.json())
    assert created.json()["email"] == "yeni@demo.test"
    dup = manager_client.post("/api/v1/admin/employees", headers=CSRF, json=body)
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "email_taken"
    bad = manager_client.post("/api/v1/admin/employees", headers=CSRF, json={**body, "temporary_password": "kısa"})
    assert bad.status_code == 422 and "temporary_password" in bad.json()["error"]["details"]["fields"]

    from fastapi.testclient import TestClient

    from app.main import create_app

    new = TestClient(create_app())
    login = {"email": "yeni@demo.test", "password": "gecici-123"}
    assert new.post("/api/v1/auth/login", headers=CSRF, json=login).status_code == 200
    emp_id = created.json()["id"]
    detail = manager_client.get(f"/api/v1/admin/employees/{emp_id}").json()
    assert_contract("EmployeeDetail", detail)

    off = manager_client.post(f"/api/v1/admin/employees/{emp_id}/deactivate", headers=CSRF)
    assert off.status_code == 200 and off.json()["active"] is False
    assert new.get("/api/v1/me").status_code == 401  # açık oturum kapandı
    assert new.post("/api/v1/auth/login", headers=CSRF, json=login).status_code == 401
    inactive = manager_client.get("/api/v1/admin/employees", params={"active": "false"}).json()["items"]
    assert [e["id"] for e in inactive] == [emp_id]


def test_manager_cannot_be_targeted_as_employee(manager_client):
    me = manager_client.get("/api/v1/me").json()["user"]["id"]
    assert manager_client.get(f"/api/v1/admin/employees/{me}").status_code == 404
    assert manager_client.post(f"/api/v1/admin/employees/{me}/deactivate", headers=CSRF).status_code == 404


def test_assignments_skip_open_and_reject_unknown(manager_client, elif_client):
    training = next(t for t in manager_client.get("/api/v1/trainings").json()["items"]
                    if t["title"] == "Fişsiz iade talebi")
    emps = {e["email"]: e["id"] for e in manager_client.get("/api/v1/admin/employees").json()["items"]}
    body = {"training_id": training["id"], "employee_ids": [emps["elif@demo.test"], emps["can@demo.test"]],
            "due_at": "2026-10-25T18:00:00Z"}
    res = manager_client.post("/api/v1/admin/assignments", headers=CSRF, json=body)
    assert res.status_code == 201
    assert_contract("CreateAssignmentsResponse", res.json())
    assert res.json()["skipped_employee_ids"] == [emps["elif@demo.test"]]  # seed'den açık ataması var
    assert [a["employee_id"] for a in res.json()["created"]] == [emps["can@demo.test"]]

    can = _client("can@demo.test")
    assert can.get("/api/v1/assignments").json()["items"][0]["training"]["id"] == training["id"]
    unknown = manager_client.post("/api/v1/admin/assignments", headers=CSRF,
                                  json={**body, "employee_ids": ["01JA0000000000000000000XXX"]})
    assert unknown.status_code == 404


def test_session_list_filters_and_ready_report(manager_client, elif_client):
    sid = _finished_session(elif_client)
    page = manager_client.get("/api/v1/admin/sessions").json()
    assert_contract("SessionSummaryPage", page)
    assert page["items"][0]["id"] == sid and page["items"][0]["total"]["score"] == 8.0

    def ids(**params):
        return [s["id"] for s in manager_client.get("/api/v1/admin/sessions", params=params).json()["items"]]

    assert ids(evaluation_status="ready") == [sid]
    assert ids(evaluation_status="needs_review") == []
    assert ids(review_status="not_required") == [sid]
    assert ids(review_status="pending") == []
    elif_id = elif_client.get("/api/v1/me").json()["user"]["id"]
    assert ids(employee_id=elif_id) == [sid]
    assert ids(from_="2099-01-01T00:00:00Z") == [sid]  # bilinmeyen parametre yok sayılır
    assert ids(**{"from": "2099-01-01T00:00:00Z"}) == []


def test_review_flow_for_unverified_report(manager_client, elif_client):
    sid = _finished_session(elif_client, model=UnverifiableEvaluator())
    ev = elif_client.get(f"/api/v1/sessions/{sid}/evaluation").json()
    assert ev["status"] == "needs_review" and "unverified_evidence" in ev["report"]["flags"]
    assert manager_client.get("/api/v1/admin/overview").json()["sessions_pending_review"] == 1
    pending = manager_client.get("/api/v1/admin/sessions", params={"review_status": "pending"}).json()["items"]
    assert [s["id"] for s in pending] == [sid]

    url = f"/api/v1/admin/sessions/{sid}/reviews"
    adj = {"dimension_id": "empathy", "score": 1, "reason": "yeterince uzun gerekçe"}
    bad = manager_client.post(url, headers=CSRF, json={"decision": "approved", "comment": "", "adjustments": [adj]})
    assert bad.status_code == 422
    unknown = manager_client.post(url, headers=CSRF, json={"decision": "adjusted", "comment": "", "adjustments": [
        {"dimension_id": "uydurma", "score": 1, "reason": "yeterince uzun gerekçe"}]})
    assert unknown.status_code == 422
    short = manager_client.post(url, headers=CSRF, json={"decision": "adjusted", "comment": "", "adjustments": [
        {"dimension_id": "empathy", "score": 1, "reason": "kısa"}]})
    assert short.status_code == 422

    res = manager_client.post(url, headers=CSRF, json={
        "decision": "adjusted", "comment": "Ses kaydını dinledim.",
        "adjustments": [{"dimension_id": "empathy", "score": 1, "reason": "Müşterinin sinirini hiç kabul etmedi."}]})
    assert res.status_code == 201
    assert_contract("ManagerReview", res.json())
    assert res.json()["adjustments"][0]["original_score"] == 3

    ev = elif_client.get(f"/api/v1/sessions/{sid}/evaluation").json()  # çalışan da görür
    assert_contract("EvaluationEnvelope", ev)
    assert ev["report"]["manager_review"]["id"] == res.json()["id"]
    assert ev["report"]["total"]["score"] == 12 and ev["report"]["effective_total"]["score"] == 10
    assert ev["report"]["dimensions"][0]["score"] == 3  # model raporu korunur
    summary = manager_client.get("/api/v1/admin/sessions").json()["items"][0]
    assert summary["review_status"] == "reviewed" and summary["total"]["score"] == 10
    assert manager_client.get("/api/v1/admin/overview").json()["sessions_pending_review"] == 0


def test_review_requires_evaluation(manager_client, elif_client):
    sid = _start(elif_client)["session"]["id"]
    res = manager_client.post(f"/api/v1/admin/sessions/{sid}/reviews", headers=CSRF,
                              json={"decision": "approved", "comment": "", "adjustments": []})
    assert res.status_code == 409 and res.json()["error"]["code"] == "evaluation_not_ready"


def test_draft_generate_edit_publish(manager_client, elif_client):
    res = manager_client.post("/api/v1/admin/training-drafts", headers=CSRF, json={"form": FORM})
    assert res.status_code == 202
    draft = res.json()
    assert_contract("TrainingDraft", draft)
    assert draft["status"] == "generating" and draft["content"] is None

    assert run_once()
    job = manager_client.get(f"/api/v1/jobs/{draft['generation_job_id']}").json()
    assert_contract("Job", job)
    assert job["result"] == {"kind": "draft_generation", "draft_id": draft["id"]}
    draft = manager_client.get(f"/api/v1/admin/training-drafts/{draft['id']}").json()
    assert_contract("TrainingDraft", draft)
    assert draft["status"] == "ready" and len(draft["content"]["scenarios"]) == 2
    # politikalar modelden değil formdan, aynen
    assert [(p["id"], p["body"]) for p in draft["content"]["policies"]] == [
        ("policy_1", FORM["policies"][0]["body"]), ("policy_2", FORM["policies"][1]["body"])]

    url = f"/api/v1/admin/training-drafts/{draft['id']}"
    content = draft["content"]
    content["scenarios"][0]["title"] = "Yanlış sipariş"
    content["scenarios"][0]["visible_policy_ids"] = ["policy_9"]
    stale = manager_client.patch(url, headers=CSRF, json={"version": 99, "content": content})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "version_mismatch"
    broken = {**content, "rubric": {"dimensions": [{**content["rubric"]["dimensions"][0], "levels": ["tek"]}]}}
    invalid = manager_client.patch(url, headers=CSRF, json={"version": 1, "content": broken})
    assert invalid.status_code == 422 and "content" in invalid.json()["error"]["details"]["fields"]

    saved = manager_client.patch(url, headers=CSRF, json={"version": 1, "content": content}).json()
    assert_contract("TrainingDraft", saved)
    assert saved["version"] == 2 and "policy_9" in saved["warnings"][0]

    old = manager_client.post(f"{url}/publish", headers=CSRF, json={"version": 1})
    assert old.status_code == 409
    pub = manager_client.post(f"{url}/publish", headers=CSRF, json={"version": 2})
    assert pub.status_code == 200
    assert_contract("PublishDraftResponse", pub.json())
    assert pub.json()["draft"]["status"] == "published"
    new_ids = pub.json()["draft"]["published_training_ids"]
    again = manager_client.post(f"{url}/publish", headers=CSRF, json={"version": 2}).json()
    assert again["draft"]["published_training_ids"] == new_ids  # idempotent, kopya yok

    trainings = elif_client.get("/api/v1/trainings", params={"sector": "cafe"}).json()["items"]
    assert {t["id"] for t in trainings} == set(new_ids)
    detail = elif_client.get(f"/api/v1/trainings/{new_ids[0]}").json()
    assert_contract("TrainingDetail", detail)
    assert detail["title"] == "Yanlış sipariş" and detail["version"]["policy_version"].startswith("draft:")
    assert manager_client.patch(url, headers=CSRF, json={"version": 2, "content": content}).status_code == 409

    # yayımlanan eğitimle gerçek bir oturum başlar; bilinmeyen politika atfı ayıklanmıştır
    from app.db import get_sessionmaker
    from app.models import Training

    with get_sessionmaker()() as db:
        assert db.get(Training, new_ids[0]).scenario["visible_policy_ids"] == []


class GarbageDrafter(StubModelClient):
    def chat(self, messages, **kw):
        return "üzgünüm, JSON üretemiyorum" if kw["purpose"].startswith("draft") else super().chat(messages, **kw)


def test_draft_generation_failure_is_retryable(manager_client):
    draft = manager_client.post("/api/v1/admin/training-drafts", headers=CSRF, json={"form": FORM}).json()
    run_once(model=GarbageDrafter())
    d = manager_client.get(f"/api/v1/admin/training-drafts/{draft['id']}").json()
    assert d["status"] == "error"
    job = manager_client.get(f"/api/v1/jobs/{draft['generation_job_id']}").json()
    assert job["status"] == "error" and job["error"]["retryable"]
    assert manager_client.post(f"/api/v1/jobs/{job['id']}/retry", headers=CSRF).status_code == 202
    assert manager_client.get(f"/api/v1/admin/training-drafts/{draft['id']}").json()["status"] == "generating"
    run_once()
    assert manager_client.get(f"/api/v1/admin/training-drafts/{draft['id']}").json()["status"] == "ready"


def test_draft_form_validation(manager_client):
    res = manager_client.post("/api/v1/admin/training-drafts", headers=CSRF,
                              json={"form": {**FORM, "scenario_count": 9, "sector": "Kafe!"}})
    assert res.status_code == 422
    assert {"form.scenario_count", "form.sector"} <= set(res.json()["error"]["details"]["fields"])


def test_other_org_isolated(manager_client, env):
    """Başka organizasyonun yöneticisi hiçbir şeyi göremez."""
    from app.core.security import hash_password
    from app.db import get_sessionmaker
    from app.models import Organization, User

    with get_sessionmaker()() as db:
        org = Organization(name="Rakip")
        db.add(org)
        db.flush()
        db.add(User(org_id=org.id, email="rakip@x.test", display_name="Rakip", role="manager",
                    password_hash=hash_password(PASSWORD)))
        db.commit()
    rival = _client("rakip@x.test")
    assert rival.get("/api/v1/admin/employees").json()["items"] == []
    assert rival.get("/api/v1/trainings").json()["items"] == []
    elif_id = next(e["id"] for e in manager_client.get("/api/v1/admin/employees").json()["items"]
                   if e["email"] == "elif@demo.test")
    assert rival.get(f"/api/v1/admin/employees/{elif_id}").status_code == 404
