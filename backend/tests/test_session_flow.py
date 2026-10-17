import uuid

import pytest

from app.services.model_client import ModelUnavailable, StubModelClient
from app.worker.jobs import run_once
from tests.conftest import CSRF, assert_contract, make_audio


def _retail_training(client) -> dict:
    items = client.get("/api/v1/trainings", params={"sector": "retail"}).json()["items"]
    return next(t for t in items if t["title"] == "Fişsiz iade talebi")


def _start(client) -> dict:
    t = _retail_training(client)
    a = client.get("/api/v1/assignments").json()["items"][0]
    res = client.post("/api/v1/sessions", headers=CSRF, json={
        "training_id": t["id"], "assignment_id": a["id"], "client_request_id": str(uuid.uuid4())})
    assert res.status_code == 201, res.text
    return res.json()


def _upload(client, session_id: str, audio: bytes | None = None, crid: str | None = None,
            mime: str = "audio/webm;codecs=opus"):
    return client.post(f"/api/v1/sessions/{session_id}/turns", headers=CSRF,
                       files={"audio": ("kayit.webm", audio or make_audio(), mime)},
                       data={"client_request_id": crid or str(uuid.uuid4())})


def test_trainings_and_assignments_match_contract(elif_client):
    page = elif_client.get("/api/v1/trainings").json()
    assert_contract("TrainingPage", page)
    assert len(page["items"]) == 6
    assert {t["sector"] for t in page["items"]} == {"retail", "hotel"}

    detail = elif_client.get(f"/api/v1/trainings/{page['items'][0]['id']}").json()
    assert_contract("TrainingDetail", detail)
    assert "hidden_goal" not in str(detail) and "mood" not in detail["customer"]

    assignments = elif_client.get("/api/v1/assignments").json()
    assert_contract("AssignmentPage", assignments)
    assert assignments["items"][0]["status"] == "assigned"


def test_pagination_cursor(elif_client):
    first = elif_client.get("/api/v1/trainings", params={"limit": 4}).json()
    assert len(first["items"]) == 4 and first["next_cursor"]
    second = elif_client.get("/api/v1/trainings", params={"limit": 4, "cursor": first["next_cursor"]}).json()
    assert len(second["items"]) == 2 and second["next_cursor"] is None
    assert not {t["id"] for t in first["items"]} & {t["id"] for t in second["items"]}


def test_full_voice_turn_and_evaluation_flow(elif_client):
    created = _start(elif_client)
    assert_contract("CreateSessionResponse", created)
    session = created["session"]
    assert session["turns"][0]["speaker"] == "customer" and session["turns"][0]["text"]
    assert created["opening_job_id"] is None  # testte TTS kapalı

    accepted = _upload(elif_client, session["id"])
    assert accepted.status_code == 202, accepted.text
    assert_contract("TurnAccepted", accepted.json())
    job_id = accepted.json()["job_id"]

    queued = elif_client.get(f"/api/v1/jobs/{job_id}").json()
    assert_contract("Job", queued)
    assert queued["status"] == "queued"
    busy = _upload(elif_client, session["id"])
    assert busy.status_code == 409 and busy.json()["error"]["code"] == "turn_in_progress"

    assert run_once()
    job = elif_client.get(f"/api/v1/jobs/{job_id}").json()
    assert_contract("Job", job)
    assert job["status"] == "ready", job
    assert job["result"]["employee_turn"]["text"].startswith("[stub transkript]")
    assert job["result"]["customer_turn"]["speaker"] == "customer"

    s = elif_client.get(f"/api/v1/sessions/{session['id']}").json()
    assert_contract("Session", s)
    assert [t["speaker"] for t in s["turns"]] == ["customer", "employee", "customer"]
    assert s["employee_turn_count"] == 1 and s["pending_job_id"] is None

    # çalışanın kendi kaydı oynatılabilir
    emp_turn = s["turns"][1]
    assert emp_turn["has_audio"]
    audio = elif_client.get(f"/api/v1/sessions/{session['id']}/turns/{emp_turn['id']}/audio")
    assert audio.status_code == 200 and audio.headers["content-type"].startswith("audio/webm")

    not_finished = elif_client.get(f"/api/v1/sessions/{session['id']}/evaluation")
    assert not_finished.status_code == 409

    fin = elif_client.post(f"/api/v1/sessions/{session['id']}/finish", headers=CSRF)
    assert fin.status_code == 202
    assert_contract("FinishAccepted", fin.json())
    again = elif_client.post(f"/api/v1/sessions/{session['id']}/finish", headers=CSRF)
    assert again.json() == fin.json()  # idempotent

    pending = elif_client.get(f"/api/v1/sessions/{session['id']}/evaluation").json()
    assert_contract("EvaluationEnvelope", pending)
    assert pending["status"] == "pending"
    assert _upload(elif_client, session["id"]).json()["error"]["code"] == "session_not_active"

    assert run_once()
    ev = elif_client.get(f"/api/v1/sessions/{session['id']}/evaluation").json()
    assert_contract("EvaluationEnvelope", ev)
    report = ev["report"]
    assert ev["status"] == "ready", report["flags"]
    assert [d["dimension_id"] for d in report["dimensions"]] == ["empathy", "policy_accuracy", "solution", "clarity"]
    assert all(e["verified"] for d in report["dimensions"] for e in d["evidence"])
    assert report["total"] == {"score": 8.0, "max_score": 16.0, "complete": True,
                               "scored_dimensions": 4, "total_dimensions": 4}
    assert "short_session" in report["flags"]
    assert report["model_run"]["runtime"] == "stub"

    a = elif_client.get("/api/v1/assignments").json()["items"][0]
    assert a["status"] == "completed" and a["completed_session_id"] == session["id"]


def test_turn_upload_is_idempotent(elif_client):
    session = _start(elif_client)["session"]
    crid = str(uuid.uuid4())
    first = _upload(elif_client, session["id"], crid=crid)
    second = _upload(elif_client, session["id"], crid=crid)
    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()


def test_create_session_is_idempotent(elif_client):
    t = _retail_training(elif_client)
    body = {"training_id": t["id"], "client_request_id": str(uuid.uuid4())}
    a = elif_client.post("/api/v1/sessions", headers=CSRF, json=body)
    b = elif_client.post("/api/v1/sessions", headers=CSRF, json=body)
    assert (a.status_code, b.status_code) == (201, 200)
    assert a.json()["session"]["id"] == b.json()["session"]["id"]


@pytest.mark.parametrize("mime,audio,status,code", [
    ("text/plain", b"merhaba", 415, "unsupported_media_type"),
    ("audio/webm", b"bu bir ses degil", 422, "audio_undecodable"),
    ("audio/wav", None, 422, "audio_too_short"),
])
def test_bad_audio_rejected(elif_client, mime, audio, status, code):
    session = _start(elif_client)["session"]
    if audio is None:
        audio = make_audio(0.2, fmt="wav")
    res = _upload(elif_client, session["id"], audio=audio, mime=mime)
    assert res.status_code == status, res.text
    assert_contract("Error", res.json())
    assert res.json()["error"]["code"] == code


def test_too_long_audio_rejected(elif_client):
    session = _start(elif_client)["session"]
    res = _upload(elif_client, session["id"], audio=make_audio(31, fmt="wav"), mime="audio/wav")
    assert res.status_code == 422 and res.json()["error"]["code"] == "audio_too_long"


def test_payload_too_large(elif_client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "max_audio_bytes", 1000)
    session = _start(elif_client)["session"]
    res = _upload(elif_client, session["id"])
    assert res.status_code == 413 and res.json()["error"]["code"] == "payload_too_large"


def test_other_employee_cannot_see_session_but_manager_can(elif_client, can_client, manager_client):
    session = _start(elif_client)["session"]
    assert can_client.get(f"/api/v1/sessions/{session['id']}").status_code == 404
    assert _upload(can_client, session["id"]).status_code == 404
    res = manager_client.get(f"/api/v1/sessions/{session['id']}")
    assert res.status_code == 200
    assert _upload(manager_client, session["id"]).status_code == 403


def test_finish_requires_an_employee_turn(elif_client):
    session = _start(elif_client)["session"]
    res = elif_client.post(f"/api/v1/sessions/{session['id']}/finish", headers=CSRF)
    assert res.status_code == 409


class FlakyModel(StubModelClient):
    def __init__(self):
        super().__init__()
        self.fail_chat = True

    def chat(self, messages, **kw):
        if self.fail_chat and kw["purpose"] == "customer_reply":
            raise ModelUnavailable("bağlantı reddedildi")
        return super().chat(messages, **kw)


def test_model_failure_is_retryable_without_reupload(elif_client):
    session = _start(elif_client)["session"]
    job_id = _upload(elif_client, session["id"]).json()["job_id"]
    model = FlakyModel()
    assert run_once(model=model)

    failed = elif_client.get(f"/api/v1/jobs/{job_id}").json()
    assert_contract("Job", failed)
    assert failed["status"] == "error"
    assert failed["error"]["code"] == "model_unavailable" and failed["error"]["retryable"]
    assert failed["error"]["failed_stage"] == "generating"
    s = elif_client.get(f"/api/v1/sessions/{session['id']}").json()
    assert s["pending_job_id"] == job_id  # sayfa yenilense de tekrar deneme bulunur
    assert s["turns"][1]["text"].startswith("[stub transkript]")  # ASR sonucu korundu

    retried = elif_client.post(f"/api/v1/jobs/{job_id}/retry", headers=CSRF)
    assert retried.status_code == 202 and retried.json()["attempt"] == 2
    model.fail_chat = False
    assert run_once(model=model)
    done = elif_client.get(f"/api/v1/jobs/{job_id}").json()
    assert done["status"] == "ready"
    turns = elif_client.get(f"/api/v1/sessions/{session['id']}").json()["turns"]
    assert len(turns) == 3


def test_retry_of_ready_job_is_noop(elif_client):
    session = _start(elif_client)["session"]
    job_id = _upload(elif_client, session["id"]).json()["job_id"]
    run_once()
    res = elif_client.post(f"/api/v1/jobs/{job_id}/retry", headers=CSRF)
    assert res.status_code == 202 and res.json()["attempt"] == 1


def test_other_users_job_is_hidden(elif_client, can_client):
    session = _start(elif_client)["session"]
    job_id = _upload(elif_client, session["id"]).json()["job_id"]
    assert can_client.get(f"/api/v1/jobs/{job_id}").status_code == 404


class ScriptedCustomer(StubModelClient):
    """Müşteri cevaplarını sırayla verir."""

    def __init__(self, replies):
        super().__init__()
        self.replies, self.calls = list(replies), 0

    def chat(self, messages, **kw):
        if kw["purpose"] == "customer_reply":
            self.calls += 1
            return self.replies.pop(0)
        return super().chat(messages, **kw)


NARRATOR = "Ayşe Hanım'ın bu yanıtı ile karşılaştığı durumu yaşamak zorunda değil.\n\nYeni bir diyalog başlatabilirsin."


def _one_turn(client, model) -> dict:
    sid = _start(client)["session"]["id"]
    job_id = _upload(client, sid).json()["job_id"]
    run_once(model=model)
    return client.get(f"/api/v1/jobs/{job_id}").json()


def test_out_of_role_reply_is_regenerated(elif_client):
    model = ScriptedCustomer([NARRATOR, "Ne demek istiyorsunuz? Paramı geri istiyorum."])
    job = _one_turn(elif_client, model)
    assert job["result"]["customer_turn"]["text"] == "Ne demek istiyorsunuz? Paramı geri istiyorum."
    assert model.calls == 2


def test_persistent_out_of_role_falls_back_to_in_role_line(elif_client):
    from app.worker.jobs import FALLBACK_REPLY

    job = _one_turn(elif_client, ScriptedCustomer([NARRATOR, "Senaryo gereği müşteri olarak tepki veririm."]))
    assert job["status"] == "ready" and job["result"]["customer_turn"]["text"] == FALLBACK_REPLY


def test_end_marker_ignored_on_first_turn(elif_client):
    job = _one_turn(elif_client, ScriptedCustomer(["Tamam, anladım. [GÖRÜŞME_BİTTİ]"]))
    assert job["result"]["customer_turn"]["text"] == "Tamam, anladım."
    assert job["result"]["session_should_end"] is False


def test_end_marker_honored_after_two_turns(elif_client):
    model = ScriptedCustomer(["Peki, sonra?", "Tamam, teşekkürler. [GÖRÜŞME_BİTTİ]"])
    sid = _start(elif_client)["session"]["id"]
    _upload(elif_client, sid)
    run_once(model=model)
    job_id = _upload(elif_client, sid).json()["job_id"]
    run_once(model=model)
    assert elif_client.get(f"/api/v1/jobs/{job_id}").json()["result"]["session_should_end"] is True
