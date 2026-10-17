import copy
import json

from app.services.model_client import StubModelClient
from app.worker.jobs import run_once
from tests.conftest import CSRF
from tests.test_admin import FORM


class WrongCountModel(StubModelClient):
    def __init__(self, repair_succeeds, missing=False):
        super().__init__()
        self.repair_succeeds = repair_succeeds
        self.missing = missing
        self.purposes = []

    def chat(self, messages, **kwargs):
        purpose = kwargs["purpose"]
        self.purposes.append(purpose)
        output = super().chat(messages, **kwargs)
        if purpose == "draft" or (purpose == "draft_repair" and not self.repair_succeeds):
            part = json.loads(output)
            if self.missing:
                part["scenarios"] = part["scenarios"][:1]
            else:
                extra = copy.deepcopy(part["scenarios"][0])
                extra["key"] = "extra_scenario"
                part["scenarios"].append(extra)
            return json.dumps(part)
        return output


def test_extra_scenarios_are_limited_to_requested_count(manager_client):
    draft = manager_client.post("/api/v1/admin/training-drafts", headers=CSRF, json={"form": FORM}).json()
    model = WrongCountModel(repair_succeeds=True)
    assert run_once(model=model)
    result = manager_client.get(f"/api/v1/admin/training-drafts/{draft['id']}").json()
    assert result["status"] == "ready"
    assert len(result["content"]["scenarios"]) == FORM["scenario_count"]
    assert model.purposes == ["draft"]
    assert result["warnings"]


def test_missing_scenarios_are_repaired(manager_client):
    draft = manager_client.post("/api/v1/admin/training-drafts", headers=CSRF, json={"form": FORM}).json()
    model = WrongCountModel(repair_succeeds=True, missing=True)
    assert run_once(model=model)
    result = manager_client.get(f"/api/v1/admin/training-drafts/{draft['id']}").json()
    assert result["status"] == "ready"
    assert len(result["content"]["scenarios"]) == FORM["scenario_count"]
    assert model.purposes == ["draft", "draft_repair"]


def test_unrepairable_scenario_count_is_retryable_error(manager_client):
    draft = manager_client.post("/api/v1/admin/training-drafts", headers=CSRF, json={"form": FORM}).json()
    assert run_once(model=WrongCountModel(repair_succeeds=False, missing=True))
    result = manager_client.get(f"/api/v1/admin/training-drafts/{draft['id']}").json()
    assert result["status"] == "error"
    assert result["content"] is None
    job = manager_client.get(f"/api/v1/jobs/{draft['generation_job_id']}").json()
    assert job["error"]["retryable"] is True
