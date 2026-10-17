"""Yönetici uçları. Hepsi `manager` rolü ister ve yalnız kendi organizasyonunu görür."""

from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import and_, exists, func, not_, or_, select
from sqlalchemy.orm import Session

from app import schemas
from app.core.errors import ApiError, conflict, not_found
from app.core.ids import utcnow
from app.core.security import hash_password, require_manager
from app.db import get_db
from app.models import (
    Assignment,
    AuthSession,
    Evaluation,
    Job,
    PracticeSession,
    Review,
    Training,
    TrainingDraft,
    User,
)
from app.services import drafts as draftsvc

router = APIRouter(prefix="/admin", tags=["admin"])
OPEN_ASSIGNMENT = ("assigned", "in_progress")
NON_ASCII_EMAIL = "E-posta adresinde Türkçe karakter (ç, ğ, ı, ö, ş, ü) kullanılamaz."


def _validation(fields: dict[str, str], message: str = "Girdi doğrulanamadı.") -> ApiError:
    return ApiError(422, "validation_error", message, {"fields": fields})


# ---------------------------------------------------------------- özet

@router.get("/overview")
def overview(me: User = Depends(require_manager), db: Session = Depends(get_db)):
    org = me.org_id
    reviewed = exists().where(Review.session_id == Evaluation.session_id)
    return {
        "active_employees": db.query(User).filter_by(org_id=org, role="employee", active=True).count(),
        "open_assignments": db.query(Assignment).filter(Assignment.org_id == org,
                                                        Assignment.status.in_(OPEN_ASSIGNMENT)).count(),
        "completed_assignments": db.query(Assignment).filter_by(org_id=org, status="completed").count(),
        "sessions_pending_review": db.query(Evaluation).join(PracticeSession)
        .filter(PracticeSession.org_id == org, Evaluation.status == "needs_review", not_(reviewed)).count(),
        "sessions_last_7_days": db.query(PracticeSession)
        .filter(PracticeSession.org_id == org, PracticeSession.started_at >= utcnow() - timedelta(days=7)).count(),
    }


# ---------------------------------------------------------------- çalışanlar

class CreateEmployeeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    display_name: str = Field(min_length=1, max_length=100)
    temporary_password: str = Field(min_length=8, max_length=200)


def _employee(db: Session, me: User, employee_id: str) -> User:
    u = db.get(User, employee_id)
    if u is None or u.org_id != me.org_id or u.role != "employee":
        raise not_found("Çalışan")
    return u


@router.get("/employees")
def list_employees(cursor: str | None = None, limit: int = Query(20, ge=1, le=100),
                   q: str | None = Query(None, max_length=100), active: bool | None = None,
                   me: User = Depends(require_manager), db: Session = Depends(get_db)):
    stmt = select(User).where(User.org_id == me.org_id, User.role == "employee")
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(User.display_name).like(like), func.lower(User.email).like(like)))
    if active is not None:
        stmt = stmt.where(User.active.is_(active))
    rows, nxt = schemas.paginate(db, stmt, User.id, cursor, limit, desc=False)
    return {"items": [schemas.employee_json(db, r[0]) for r in rows], "next_cursor": nxt}


@router.post("/employees", status_code=201)
def create_employee(body: CreateEmployeeRequest, me: User = Depends(require_manager), db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    # Tarayıcıların type="email" alanı ASCII dışı yerel kısmı reddediyor; böyle bir kullanıcı oluşturulsa
    # giriş sayfasından giriş yapamaz. Çoğu e-posta sistemi de desteklemiyor.
    if not email.isascii():
        raise _validation({"email": NON_ASCII_EMAIL}, NON_ASCII_EMAIL)
    if db.query(User.id).filter(func.lower(User.email) == email).first():
        raise conflict("email_taken", "Bu e-posta adresiyle bir kullanıcı zaten var.")
    u = User(org_id=me.org_id, email=email, display_name=body.display_name.strip(), role="employee",
             password_hash=hash_password(body.temporary_password))
    db.add(u)
    db.commit()
    return schemas.employee_json(db, u)


@router.get("/employees/{employee_id}")
def get_employee(employee_id: str, me: User = Depends(require_manager), db: Session = Depends(get_db)):
    u = _employee(db, me, employee_id)
    assignments = db.query(Assignment).filter_by(employee_id=u.id).order_by(Assignment.id.desc()).all()
    sessions = (db.query(PracticeSession).filter_by(employee_id=u.id)
                .order_by(PracticeSession.id.desc()).limit(20).all())
    return {
        **schemas.employee_json(db, u),
        "assignments": [schemas.assignment_json(a, db.get(Training, a.training_id)) for a in assignments],
        "recent_sessions": [schemas.session_summary(db, s) for s in sessions],
    }


@router.post("/employees/{employee_id}/deactivate")
def deactivate_employee(employee_id: str, me: User = Depends(require_manager), db: Session = Depends(get_db)):
    u = _employee(db, me, employee_id)
    u.active = False
    db.query(AuthSession).filter_by(user_id=u.id).delete()  # açık oturumları hemen kapat
    db.commit()
    return schemas.employee_json(db, u)


# ---------------------------------------------------------------- oturumlar ve inceleme

@router.get("/sessions")
def list_sessions(cursor: str | None = None, limit: int = Query(20, ge=1, le=100),
                  employee_id: str | None = None, training_id: str | None = None,
                  evaluation_status: Literal["pending", "ready", "needs_review", "error"] | None = None,
                  review_status: Literal["not_required", "pending", "reviewed"] | None = None,
                  from_: datetime | None = Query(None, alias="from"), to: datetime | None = None,
                  me: User = Depends(require_manager), db: Session = Depends(get_db)):
    stmt = (select(PracticeSession).outerjoin(Evaluation, Evaluation.session_id == PracticeSession.id)
            .where(PracticeSession.org_id == me.org_id))
    if employee_id:
        stmt = stmt.where(PracticeSession.employee_id == employee_id)
    if training_id:
        stmt = stmt.where(PracticeSession.training_id == training_id)
    if evaluation_status:
        stmt = stmt.where(Evaluation.status == evaluation_status)
    if review_status:
        # review_status saklanmaz; evaluation_state() ile aynı kuraldan türetilir.
        has_review = exists().where(Review.session_id == PracticeSession.id)
        needs = Evaluation.status == "needs_review"
        cond = {"reviewed": has_review,
                "pending": and_(needs, not_(has_review)),
                "not_required": and_(not_(has_review), or_(Evaluation.status.is_(None), not_(needs)))}
        stmt = stmt.where(cond[review_status])
    if from_:
        stmt = stmt.where(PracticeSession.started_at >= from_)
    if to:
        stmt = stmt.where(PracticeSession.started_at <= to)
    rows, nxt = schemas.paginate(db, stmt, PracticeSession.id, cursor, limit, desc=True)
    return {"items": [schemas.session_summary(db, r[0]) for r in rows], "next_cursor": nxt}


class DimensionAdjustment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dimension_id: str
    score: int | None = Field(ge=0, le=4)
    reason: str = Field(min_length=10, max_length=1000)


class CreateReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "adjusted"]
    adjustments: list[DimensionAdjustment]
    comment: str = Field(max_length=2000)


@router.post("/sessions/{session_id}/reviews", status_code=201)
def create_review(session_id: str, body: CreateReviewRequest, me: User = Depends(require_manager),
                  db: Session = Depends(get_db)):
    s = db.get(PracticeSession, session_id)
    if s is None or s.org_id != me.org_id:
        raise not_found("Oturum")
    ev = db.get(Evaluation, s.id)
    if ev is None or ev.status not in ("ready", "needs_review") or ev.report is None:
        raise conflict("evaluation_not_ready", "Değerlendirme hazır olmadan inceleme yapılamaz.")
    if body.decision == "approved" and body.adjustments:
        raise _validation({"adjustments": "Onaylanan incelemede düzeltme olmamalı."})
    if body.decision == "adjusted" and not body.adjustments:
        raise _validation({"adjustments": "En az bir boyut düzeltilmeli."})
    original = {d["dimension_id"]: d["score"] for d in ev.report["dimensions"]}
    ids = [a.dimension_id for a in body.adjustments]
    if len(set(ids)) != len(ids):
        raise _validation({"adjustments": "Aynı boyut birden fazla kez düzeltilemez."})
    unknown = [i for i in ids if i not in original]
    if unknown:
        raise _validation({"adjustments": f"Bilinmeyen boyut: {', '.join(unknown)}"})

    adjustments = [{"dimension_id": a.dimension_id, "score": a.score, "original_score": original[a.dimension_id],
                    "reason": a.reason.strip()} for a in body.adjustments]
    r = Review(session_id=s.id, reviewer_id=me.id, decision=body.decision, comment=body.comment.strip(),
               adjustments=adjustments)
    db.add(r)
    db.commit()
    return schemas.review_json(db, r)


# ---------------------------------------------------------------- atama

class CreateAssignmentsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    training_id: str
    employee_ids: list[str] = Field(min_length=1, max_length=200)
    channel: Literal["message", "phone"] = "message"
    due_at: datetime | None = None


@router.post("/assignments", status_code=201)
def create_assignments(body: CreateAssignmentsRequest, me: User = Depends(require_manager),
                       db: Session = Depends(get_db)):
    if len(set(body.employee_ids)) != len(body.employee_ids):
        raise _validation({"employee_ids": "Aynı çalışan birden fazla kez seçilmiş."})
    t = db.get(Training, body.training_id)
    if t is None or t.org_id != me.org_id or not t.active:
        raise not_found("Eğitim")
    employees = db.query(User).filter(User.id.in_(body.employee_ids), User.org_id == me.org_id,
                                      User.role == "employee", User.active.is_(True)).all()
    if len(employees) != len(body.employee_ids):
        raise not_found("Çalışan")
    already = {a.employee_id for a in db.query(Assignment).filter(
        Assignment.training_id == t.id, Assignment.employee_id.in_(body.employee_ids),
        Assignment.channel == body.channel, Assignment.status.in_(OPEN_ASSIGNMENT))}
    created = []
    for emp_id in body.employee_ids:
        if emp_id not in already:
            a = Assignment(org_id=me.org_id, training_id=t.id, employee_id=emp_id, assigned_by=me.id,
                           channel=body.channel, due_at=body.due_at)
            db.add(a)
            created.append(a)
    db.commit()
    return {"created": [schemas.assignment_json(a, t) for a in created],
            "skipped_employee_ids": [e for e in body.employee_ids if e in already]}


# ---------------------------------------------------------------- eğitim taslakları

def _draft(db: Session, me: User, draft_id: str) -> TrainingDraft:
    d = db.get(TrainingDraft, draft_id)
    if d is None or d.org_id != me.org_id:
        raise not_found("Taslak")
    return d


def _check_version(d: TrainingDraft, version: int) -> None:
    if d.version != version:
        raise conflict("version_mismatch", "Taslak başka biri tarafından değiştirilmiş. Sayfayı yenileyin.")


class CreateTrainingDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    form: draftsvc.BusinessRulesForm


class UpdateTrainingDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)
    content: dict


class PublishDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)


@router.get("/training-drafts")
def list_drafts(cursor: str | None = None, limit: int = Query(20, ge=1, le=100),
                status: Literal["generating", "ready", "error", "published"] | None = None,
                me: User = Depends(require_manager), db: Session = Depends(get_db)):
    stmt = select(TrainingDraft).where(TrainingDraft.org_id == me.org_id)
    if status:
        stmt = stmt.where(TrainingDraft.status == status)
    rows, nxt = schemas.paginate(db, stmt, TrainingDraft.id, cursor, limit, desc=True)
    return {"items": [schemas.draft_json(r[0]) for r in rows], "next_cursor": nxt}


@router.post("/training-drafts", status_code=202)
def create_draft(body: CreateTrainingDraftRequest, me: User = Depends(require_manager), db: Session = Depends(get_db)):
    d = TrainingDraft(org_id=me.org_id, created_by=me.id, form=body.form.model_dump())
    db.add(d)
    db.flush()
    job = Job(org_id=me.org_id, owner_id=me.id, kind="draft_generation", priority=10, state={"draft_id": d.id})
    db.add(job)
    db.flush()
    d.generation_job_id = job.id
    db.commit()
    return schemas.draft_json(d)


@router.get("/training-drafts/{draft_id}")
def get_draft(draft_id: str, me: User = Depends(require_manager), db: Session = Depends(get_db)):
    return schemas.draft_json(_draft(db, me, draft_id))


@router.patch("/training-drafts/{draft_id}")
def update_draft(draft_id: str, body: UpdateTrainingDraftRequest, me: User = Depends(require_manager),
                 db: Session = Depends(get_db)):
    d = _draft(db, me, draft_id)
    if d.status != "ready":
        raise conflict("conflict", "Yalnızca hazır taslak düzenlenebilir.")
    _check_version(d, body.version)
    try:
        content = draftsvc.DraftContent.model_validate(body.content).model_dump()
    except ValidationError as exc:
        raise _validation({"content": draftsvc.validation_problem(exc)}, "Taslak içeriği geçersiz.") from exc
    d.content, d.warnings, d.version = content, draftsvc.warnings_for(content), d.version + 1
    db.commit()
    return schemas.draft_json(d)


@router.post("/training-drafts/{draft_id}/publish")
def publish_draft(draft_id: str, body: PublishDraftRequest, me: User = Depends(require_manager),
                  db: Session = Depends(get_db)):
    d = _draft(db, me, draft_id)
    if d.status == "published":  # idempotent
        trainings = [db.get(Training, i) for i in d.published_training_ids]
    else:
        if d.status != "ready" or d.content is None:
            raise conflict("conflict", "Yalnızca hazır taslak yayımlanabilir.")
        _check_version(d, body.version)
        trainings = [Training(org_id=me.org_id, **row) for row in draftsvc.training_rows(
            d.content, draft_id=d.id, version=d.version, sector=d.form["sector"])]
        db.add_all(trainings)
        db.flush()
        d.status, d.published_training_ids = "published", [t.id for t in trainings]
        db.commit()
    return {"draft": schemas.draft_json(d), "trainings": [schemas.training_summary(t) for t in trainings]}
