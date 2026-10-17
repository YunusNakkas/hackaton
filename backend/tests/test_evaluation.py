import pytest

from app.services import evaluation as ev

RUBRIC = {"dimensions": [{"id": d, "name": d, "description": "", "levels": ["0", "1", "2", "3", "4"], "weight": 1}
                         for d in ("empathy", "solution")]}
POLICIES = [{"id": "p1", "title": "Fişsiz iade", "body": "..."}]
TURNS = {
    "t0": ev.LabeledTurn("01JA000000000000000000TN00", "customer", "Fişim yok, iade istiyorum."),
    "t1": ev.LabeledTurn("01JA000000000000000000TN01", "employee", "Anlıyorum, hemen kart kaydınıza bakıyorum."),
}
RUN = {"model": "m", "runtime": "stub", "prompt_version": "evaluator@1", "generated_at": "x", "repaired": False}


def _data(**over):
    base = {
        "dimensions": [
            {"dimension_id": "empathy", "score": 3, "rationale": "r",
             "evidence": [{"turn_id": "t1", "quote": "Anlıyorum"}], "policy_refs": []},
            {"dimension_id": "solution", "score": 2, "rationale": "r",
             "evidence": [{"turn_id": "t1", "quote": "hemen kart kaydınıza bakıyorum"}], "policy_refs": ["p1"]},
        ],
        "strengths": ["s"], "improvements": ["i"],
    }
    base.update(over)
    return base


def _build(data, run=RUN):
    return ev.build_report(data, rubric=RUBRIC, rubric_version="r@1", policies=POLICIES, turns_by_label=TURNS,
                           model_run=run, employee_turn_count=3)


def test_verified_report_is_ready_and_total_computed_in_code():
    report, status = _build(_data())
    assert status == "ready" and report["flags"] == []
    assert report["total"]["score"] == 5 and report["total"]["max_score"] == 8
    assert report["dimensions"][1]["policy_refs"][0] == {"policy_id": "p1", "title": "Fişsiz iade",
                                                         "quote": None, "verified": True}
    assert report["dimensions"][0]["evidence"][0]["turn_id"] == "01JA000000000000000000TN01"


def test_quote_not_in_transcript_needs_review():
    data = _data()
    data["dimensions"][0]["evidence"] = [{"turn_id": "t1", "quote": "iadeyi hemen nakit yapalım"}]
    report, status = _build(data)
    assert status == "needs_review"
    assert {"unverified_evidence", "score_without_verified_evidence"} <= set(report["flags"])


def test_customer_quote_is_not_valid_employee_evidence():
    data = _data()
    data["dimensions"][0]["evidence"] = [{"turn_id": "t0", "quote": "Fişim yok"}]
    report, status = _build(data)
    assert status == "needs_review" and report["dimensions"][0]["evidence"][0]["verified"] is False


def test_unknown_turn_label_is_dropped():
    data = _data()
    data["dimensions"][1]["evidence"].append({"turn_id": "t99", "quote": "x"})
    report, status = _build(data)
    assert "dropped_evidence" in report["flags"] and status == "needs_review"
    assert len(report["dimensions"][1]["evidence"]) == 1


def test_unknown_policy_ref_needs_review():
    data = _data()
    data["dimensions"][1]["policy_refs"] = ["uydurma"]
    report, status = _build(data)
    assert status == "needs_review" and report["dimensions"][1]["policy_refs"][0]["verified"] is False


def test_null_score_means_no_single_total():
    data = _data()
    data["dimensions"][0].update(score=None, evidence=[])
    report, status = _build(data)
    assert status == "ready"
    assert report["total"] == {"score": None, "max_score": 8, "complete": False,
                               "scored_dimensions": 1, "total_dimensions": 2}
    assert report["dimensions"][0]["insufficient_evidence"] is True


def test_repaired_output_needs_review():
    _, status = _build(_data(), run={**RUN, "repaired": True})
    assert status == "needs_review"


def test_quote_matching_ignores_case_and_punctuation():
    assert ev.quote_in("ANLIYORUM, hemen", "Anlıyorum hemen kart kaydınıza bakıyorum.")
    assert not ev.quote_in("", "metin")


def test_parse_handles_code_fences_and_prose():
    assert ev.parse_json_output('```json\n{"a": 1}\n```') == {"a": 1}
    assert ev.parse_json_output('İşte sonuç: {"a": 2} umarım yardımcı olur') == {"a": 2}
    with pytest.raises(ev.EvaluationShapeError):
        ev.parse_json_output("JSON yok")


@pytest.mark.parametrize("bad,msg", [
    ({"dimensions": [{"dimension_id": "empathy", "score": 3}]}, "boyutlar"),
    ({"dimensions": [{"dimension_id": "empathy", "score": 5}, {"dimension_id": "solution", "score": 1}]}, "score"),
    ({"dimensions": [{"dimension_id": "empathy", "score": True}, {"dimension_id": "solution", "score": 1}]}, "score"),
    ({"dimensions": "x"}, "dimensions"),
])
def test_check_shape_rejects(bad, msg):
    with pytest.raises(ev.EvaluationShapeError, match=msg):
        ev.check_shape(bad, ["empathy", "solution"])


def test_manager_review_changes_effective_total_only():
    report, _ = _build(_data())
    review = {"adjustments": [{"dimension_id": "empathy", "score": 1, "original_score": 3, "reason": "..."}]}
    out = ev.apply_review(report, review, RUBRIC)
    assert out["total"]["score"] == 5 and out["effective_total"]["score"] == 3
    assert report["dimensions"][0]["score"] == 3  # saklanan rapor değişmez
