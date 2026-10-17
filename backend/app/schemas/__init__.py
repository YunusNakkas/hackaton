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
from app.models import Assignment, Job, Organization, PracticeSession, Training, Turn, User

ACTIVE_JOB_STATES = ("queued", "transcribing", "generating", "synthesizing", "evaluating")
JOB_POLL_MS = {"opening": 500, "turn": 750, "evaluation": 2000, "draft_generation": 2000}


def me(user: User, org: Organization) -> dict[str, Any]:
    return {"user": user_json(user), "organization": {"id": org.id, "name": org.name}}


def user_json(u: User) -> dict[str, Any]:
    return {"id": u.id, "email": u.email, "display_name": u.display_name, "role": u.role, "active": u.active}


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
        "assignment_id": s.assignment_id, "status": s.status,
        "evaluation_status": evaluation_status, "review_status": review_status,
        "versions": versions(t, s.prompt_version),
        "turns": [turn_json(x) for x in turns],
        "employee_turn_count": sum(1 for x in turns if x.speaker == "employee" and x.status == "ready"),
        "max_turns": t.max_turns, "pending_job_id": pending,
        "started_at": iso(s.started_at), "finished_at": iso(s.finished_at),
    }


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
