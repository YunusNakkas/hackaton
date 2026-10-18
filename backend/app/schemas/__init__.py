"""Veritabanı satırlarını contracts/openapi.yaml şekillerine çevirir.

Şekil doğruluğu tests/ içinde OpenAPI şemalarına karşı doğrulanır; burada ayrı Pydantic
modelleri tutulmaz ki sözleşme iki yerde farklılaşmasın.
"""

import base64
from typing import Any

from sqlalchemy import Select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.ids import iso
from app.models import Assignment, Evaluation, Job, Organization, PracticeSession, Training, Turn, User

ACTIVE_JOB_STATES = ("queued", "transcribing", "generating", "synthesizing", "evaluating")
JOB_POLL_MS = {"opening": 500, "turn": 750, "evaluation": 2000, "draft_generation": 2000, "policy_extraction": 2000}


def me(user: User, org: Organization) -> dict[str, Any]:
    return {"user": user_json(user), "organization": {"id": org.id, "name": org.name}}


def user_json(u: User) -> dict[str, Any]:
    return {"id": u.id, "email": u.email, "display_name": u.display_name, "role": u.role,
            "active": u.active, "must_change_password": u.must_change_password}


def training_summary(t: Training) -> dict[str, Any]:
    return {
        "id": t.id, "title": t.title, "sector": t.sector, "language": t.language,
        "difficulty": t.difficulty, "summary": t.summary,
        "estimated_minutes": t.estimated_minutes, "max_turns": t.max_turns,
    }


def versions(t: Training, prompt_version: str) -> dict[str, str]:
    return {"scenario_version": t.scenario_version, "policy_version": t.policy_version,
            "rubric_version": t.rubric_version, "prompt_version": prompt_version}


def training_detail(t: Training, prompt_version: str) -> dict[str, Any]:
    c = t.scenario["customer"]
    return {
        **training_summary(t),
        "customer": {"name": c["name"], "context": c["context"]},  # gizli hedef ve ruh hâli yok
        "rubric_dimensions": [{"id": d["id"], "name": d["name"], "description": d["description"]}
                              for d in t.rubric["dimensions"]],
        "version": versions(t, prompt_version),
    }


def assignment_json(a: Assignment, t: Training) -> dict[str, Any]:
    return {
        "id": a.id, "training": training_summary(t), "employee_id": a.employee_id, "status": a.status,
        "channel": a.channel,
        "assigned_at": iso(a.assigned_at), "due_at": iso(a.due_at), "completed_session_id": a.completed_session_id,
    }


def turn_json(t: Turn) -> dict[str, Any]:
    return {
        "id": t.id, "index": t.index, "speaker": t.speaker, "status": t.status, "text": t.text,
        "has_audio": t.audio_path is not None and t.status == "ready",
        "duration_ms": t.duration_ms, "created_at": iso(t.created_at),
    }


def session_json(db: Session, s: PracticeSession, evaluation_status: str | None,
                 review_status: str) -> dict[str, Any]:
    t = db.get(Training, s.training_id)
    emp = db.get(User, s.employee_id)
    turns = db.query(Turn).filter_by(session_id=s.id).order_by(Turn.index).all()
    # Çalışan bekleyen işi veya tekrar denenebilir son hatayı sayfa yenilendiğinde bulabilsin.
    last_job = (db.query(Job).filter(Job.session_id == s.id, Job.kind.in_(("opening", "turn")))
                .order_by(Job.id.desc()).first())
    pending = last_job.id if last_job and last_job.status != "ready" else None
    return {
        "id": s.id, "training": training_summary(t),
        "employee": {"id": emp.id, "display_name": emp.display_name},
        "assignment_id": s.assignment_id, "channel": s.channel, "status": s.status,
        "evaluation_status": evaluation_status, "review_status": review_status,
        "versions": versions(t, s.prompt_version),
        "turns": [turn_json(x) for x in turns],
        "employee_turn_count": sum(1 for x in turns if x.speaker == "employee" and x.status == "ready"),
        "max_turns": t.max_turns, "pending_job_id": pending, "practice": practice_json(s, t),
        "started_at": iso(s.started_at), "finished_at": iso(s.finished_at),
    }


def practice_json(s: PracticeSession, t: Training) -> dict[str, Any] | None:
    if not s.practice_mode:
        return None
    dims = {d["id"]: d for d in t.rubric["dimensions"]}
    focus = [{"id": d["id"], "name": d["name"], "description": d["description"]}
             for f in (s.practice_focus or []) if (d := dims.get(f))]
    return {"of_session_id": s.practice_of_session_id, "mode": s.practice_mode, "focus_dimensions": focus}


def evaluation_state(db: Session, s: PracticeSession) -> tuple[str | None, str]:
    """(evaluation_status, review_status). İnceleme `needs_review` raporlarda zorunludur."""
    from app.models import Evaluation, Review  # döngüsel import yok; okunabilirlik için yerel

    ev = db.get(Evaluation, s.id)
    if ev is None:
        return None, "not_required"
    if db.query(Review.id).filter_by(session_id=s.id).first():
        return ev.status, "reviewed"
    return ev.status, "pending" if ev.status == "needs_review" else "not_required"


def job_json(j: Job) -> dict[str, Any]:
    return {
        "id": j.id, "kind": j.kind, "status": j.status, "attempt": j.attempt,
        "poll_after_ms": JOB_POLL_MS.get(j.kind, 1000),
        "created_at": iso(j.created_at), "updated_at": iso(j.updated_at),
        "result": j.result if j.status == "ready" else None,
        "error": j.error if j.status == "error" else None,
    }


# ---------------------------------------------------------------- sayfalama

def encode_cursor(last_id: str) -> str:
    return base64.urlsafe_b64encode(last_id.encode()).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> str | None:
    if not cursor:
        return None
    try:
        return base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
    except (ValueError, UnicodeDecodeError) as exc:
        raise ApiError(422, "validation_error", "Geçersiz cursor.", {"fields": {"cursor": "Geçersiz"}}) from exc


def paginate(db: Session, stmt: Select, id_col, cursor: str | None, limit: int, *, desc: bool):
    """id sırasıyla (ULID zamana göre sıralı) keyset sayfalama. (satırlar, next_cursor) döner."""
    after = decode_cursor(cursor)
    if after:
        stmt = stmt.where(id_col < after if desc else id_col > after)
    stmt = stmt.order_by(id_col.desc() if desc else id_col.asc()).limit(limit + 1)
    rows = list(db.execute(stmt).all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1][0].id) if has_more and rows else None
    return rows, next_cursor


# ---------------------------------------------------------------- yönetici

def review_json(db: Session, r) -> dict[str, Any]:
    reviewer = db.get(User, r.reviewer_id)
    return {"id": r.id, "reviewer": {"id": reviewer.id, "display_name": reviewer.display_name},
            "decision": r.decision, "adjustments": r.adjustments, "comment": r.comment,
            "created_at": iso(r.created_at)}


def latest_review(db: Session, session_id: str):
    from app.models import Review

    return db.query(Review).filter_by(session_id=session_id).order_by(Review.id.desc()).first()


def effective_total(db: Session, s: PracticeSession) -> dict[str, Any] | None:
    from app.models import Evaluation
    from app.services.evaluation import apply_review

    ev = db.get(Evaluation, s.id)
    if ev is None or ev.report is None:
        return None
    r = latest_review(db, s.id)
    t = db.get(Training, s.training_id)
    return apply_review(ev.report, review_json(db, r) if r else None, t.rubric)["effective_total"]


def session_summary(db: Session, s: PracticeSession) -> dict[str, Any]:
    ev_status, review_status = evaluation_state(db, s)
    emp = db.get(User, s.employee_id)
    turns = db.query(Turn).filter_by(session_id=s.id, speaker="employee", status="ready").count()
    return {
        "id": s.id, "training": training_summary(db.get(Training, s.training_id)),
        "employee": {"id": emp.id, "display_name": emp.display_name},
        "status": s.status, "evaluation_status": ev_status, "review_status": review_status,
        "channel": s.channel,
        "total": effective_total(db, s), "employee_turn_count": turns, "practice_mode": s.practice_mode,
        "model_runtime": _model_runtime(db, s),
        "started_at": iso(s.started_at), "finished_at": iso(s.finished_at),
    }


def _model_runtime(db: Session, s: PracticeSession) -> str | None:
    ev = db.get(Evaluation, s.id)
    if ev is None or not ev.report:
        return None
    return (ev.report.get("model_run") or {}).get("runtime")


def employee_json(db: Session, u: User) -> dict[str, Any]:
    open_count = (db.query(Assignment)
                  .filter(Assignment.employee_id == u.id, Assignment.status.in_(("assigned", "in_progress"))).count())
    completed = (db.query(PracticeSession)
                 .filter_by(employee_id=u.id, status="finished")
                 .join(Evaluation, Evaluation.session_id == PracticeSession.id)
                 .count())
    active_sessions = db.query(PracticeSession).filter_by(employee_id=u.id, status="active").count()
    last = db.query(PracticeSession.started_at).filter_by(employee_id=u.id).order_by(PracticeSession.id.desc()).first()
    return {
        "id": u.id, "email": u.email, "display_name": u.display_name, "active": u.active,
        "created_at": iso(u.created_at), "open_assignments": open_count,
        "active_sessions": active_sessions,
        "completed_sessions": completed, "last_session_at": iso(last[0]) if last else None,
    }


def draft_json(d) -> dict[str, Any]:
    return {
        "id": d.id, "status": d.status, "version": d.version, "form": d.form, "content": d.content,
        "generation_job_id": d.generation_job_id, "warnings": d.warnings or [],
        "created_at": iso(d.created_at), "updated_at": iso(d.updated_at),
        "published_training_ids": d.published_training_ids or [],
    }
