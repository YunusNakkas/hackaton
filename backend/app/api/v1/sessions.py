import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import schemas
from app.core.config import get_settings
from app.core.errors import ApiError, conflict, not_found
from app.core.ids import utcnow
from app.core.security import current_user
from app.db import get_db
from app.models import Assignment, Evaluation, Job, PracticeSession, Training, Turn, User
from app.services import evaluation as evalsvc
from app.services.audio import ALLOWED_MIME, base_mime, decode_to_wav, extension_for
from app.services.prompts import CUSTOMER_VERSION

router = APIRouter(tags=["sessions"])


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    training_id: str
    assignment_id: str | None = None
    client_request_id: uuid.UUID


class SubmitMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=1000)
    client_request_id: uuid.UUID

    @field_validator("text", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


def _visible_session(db: Session, user: User, session_id: str) -> PracticeSession:
    """Sahibi çalışan veya aynı organizasyondaki yönetici görür; diğerlerine 404 (varlık sızdırılmaz)."""
    s = db.get(PracticeSession, session_id)
    if s is None or s.org_id != user.org_id or (user.role != "manager" and s.employee_id != user.id):
        raise not_found("Oturum")
    return s


def _own_session(db: Session, user: User, session_id: str) -> PracticeSession:
    s = _visible_session(db, user, session_id)
    if s.employee_id != user.id:
        raise ApiError(403, "forbidden", "Yalnızca oturumun sahibi bu işlemi yapabilir.")
    return s


def _session_body(db: Session, s: PracticeSession) -> dict:
    ev_status, review_status = schemas.evaluation_state(db, s)
    return schemas.session_json(db, s, ev_status, review_status)


@router.post("/sessions", status_code=201)
def create_session(body: CreateSessionRequest, response: Response,
                   user: User = Depends(current_user), db: Session = Depends(get_db)):
    crid = str(body.client_request_id)
    existing = db.query(PracticeSession).filter_by(employee_id=user.id, client_request_id=crid).one_or_none()
    if existing:
        if existing.training_id != body.training_id:
            raise conflict("conflict", "Bu istek kimliği farklı bir eğitim için kullanılmış.")
        response.status_code = 200
        opening = db.query(Job).filter_by(session_id=existing.id, kind="opening").one_or_none()
        return {"session": _session_body(db, existing), "opening_job_id": opening.id if opening else None}

    t = db.get(Training, body.training_id)
    if t is None or t.org_id != user.org_id or not t.active:
        raise not_found("Eğitim")
    assignment = None
    if body.assignment_id:
        assignment = db.get(Assignment, body.assignment_id)
        if assignment is None or assignment.employee_id != user.id or assignment.training_id != t.id:
            raise not_found("Atama")
        if assignment.status == "completed":
            raise conflict("conflict", "Bu atama zaten tamamlanmış.")

    settings = get_settings()
    s = PracticeSession(org_id=user.org_id, training_id=t.id, employee_id=user.id,
                        assignment_id=assignment.id if assignment else None,
                        client_request_id=crid, prompt_version=CUSTOMER_VERSION)
    db.add(s)
    db.flush()
    needs_audio = settings.tts_provider != "none"
    opening_turn = Turn(session_id=s.id, index=0, speaker="customer", text=t.scenario["opening_line"],
                        status="processing" if needs_audio else "ready")
    db.add(opening_turn)
    db.flush()
    opening_job = None
    if needs_audio:
        opening_job = Job(org_id=user.org_id, owner_id=user.id, kind="opening", priority=0,
                          session_id=s.id, turn_id=opening_turn.id)
        db.add(opening_job)
    if assignment and assignment.status == "assigned":
        assignment.status = "in_progress"
    db.commit()
    return {"session": _session_body(db, s), "opening_job_id": opening_job.id if opening_job else None}


@router.get("/sessions/{session_id}")
def get_session(session_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _session_body(db, _visible_session(db, user, session_id))


def _active_job(db: Session, session_id: str) -> Job | None:
    return (db.query(Job).filter(Job.session_id == session_id, Job.status.in_(schemas.ACTIVE_JOB_STATES))
            .first())


@router.post("/sessions/{session_id}/turns", status_code=202)
async def submit_turn(session_id: str, audio: UploadFile = File(...), client_request_id: uuid.UUID = Form(...),
                      client_duration_ms: int | None = Form(None),
                      user: User = Depends(current_user), db: Session = Depends(get_db)):
    settings = get_settings()
    s = _own_session(db, user, session_id)
    crid = str(client_request_id)

    # İdempotency: aynı istek kimliği aynı işi döndürür, ses tekrar işlenmez.
    prev = db.query(Job).filter_by(session_id=s.id, client_request_id=crid).one_or_none()
    if prev:
        return {"job_id": prev.id, "employee_turn_id": prev.turn_id}

    if s.status != "active":
        raise conflict("session_not_active", "Bu oturum bitti; yeni cevap eklenemez.")
    if _active_job(db, s.id):
        raise conflict("turn_in_progress", "Önceki cevabınız hâlâ işleniyor. Lütfen bekleyin.")
    t = db.get(Training, s.training_id)
    done = db.query(Turn).filter_by(session_id=s.id, speaker="employee", status="ready").count()
    if done >= t.max_turns:
        raise conflict("session_not_active", "Tur sınırına ulaşıldı. Lütfen görüşmeyi bitirin.")

    mime = base_mime(audio.content_type)
    if mime not in ALLOWED_MIME:
        raise ApiError(415, "unsupported_media_type", "Bu ses biçimi desteklenmiyor.")
    data = await audio.read(settings.max_audio_bytes + 1)
    if len(data) > settings.max_audio_bytes:
        raise ApiError(413, "payload_too_large", "Ses dosyası en fazla 10 MB olabilir.")
    decoded = decode_to_wav(data, min_ms=settings.min_audio_ms, max_s=settings.max_audio_seconds)

    last_index = db.query(Turn.index).filter_by(session_id=s.id).order_by(Turn.index.desc()).first()
    turn = Turn(session_id=s.id, index=(last_index[0] + 1) if last_index else 0, speaker="employee",
                duration_ms=decoded.duration_ms, audio_mime=mime)
    db.add(turn)
    try:
        db.flush()
    except IntegrityError as exc:  # eşzamanlı iki yükleme aynı index'i almaya çalıştı
        db.rollback()
        raise conflict("turn_in_progress", "Önceki cevabınız hâlâ işleniyor. Lütfen bekleyin.") from exc

    rel_dir = Path("sessions") / s.id
    (settings.media_dir / rel_dir).mkdir(parents=True, exist_ok=True)
    original = rel_dir / f"{turn.id}.{extension_for(mime)}"
    (settings.media_dir / original).write_bytes(data)
    (settings.media_dir / rel_dir / f"{turn.id}.16k.wav").write_bytes(decoded.wav_bytes)
    turn.audio_path = str(original)

    job = Job(org_id=user.org_id, owner_id=user.id, kind="turn", priority=0, session_id=s.id,
              turn_id=turn.id, client_request_id=crid,
              state={"client_duration_ms": client_duration_ms} if client_duration_ms else {})
    db.add(job)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("turn_in_progress", "Önceki cevabınız hâlâ işleniyor. Lütfen bekleyin.") from exc
    return {"job_id": job.id, "employee_turn_id": turn.id}


@router.post("/sessions/{session_id}/messages", status_code=202)
def submit_message(session_id: str, body: SubmitMessageRequest, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    s = _own_session(db, user, session_id)
    crid = str(body.client_request_id)
    prev = db.query(Job).filter_by(session_id=s.id, client_request_id=crid).one_or_none()
    if prev:
        return {"job_id": prev.id, "employee_turn_id": prev.turn_id}
    if s.status != "active":
        raise conflict("session_not_active", "Bu oturum bitti; yeni cevap eklenemez.")
    if _active_job(db, s.id):
        raise conflict("turn_in_progress", "Önceki cevabınız hâlâ işleniyor. Lütfen bekleyin.")
    t = db.get(Training, s.training_id)
    done = db.query(Turn).filter_by(session_id=s.id, speaker="employee", status="ready").count()
    if done >= t.max_turns:
        raise conflict("session_not_active", "Tur sınırına ulaşıldı. Lütfen görüşmeyi bitirin.")

    last_index = db.query(Turn.index).filter_by(session_id=s.id).order_by(Turn.index.desc()).first()
    turn = Turn(session_id=s.id, index=(last_index[0] + 1) if last_index else 0, speaker="employee",
                text=body.text, status="processing")
    db.add(turn)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("turn_in_progress", "Önceki cevabınız hâlâ işleniyor. Lütfen bekleyin.") from exc
    job = Job(org_id=user.org_id, owner_id=user.id, kind="turn", priority=0, session_id=s.id,
              turn_id=turn.id, client_request_id=crid)
    db.add(job)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("turn_in_progress", "Önceki cevabınız hâlâ işleniyor. Lütfen bekleyin.") from exc
    return {"job_id": job.id, "employee_turn_id": turn.id}


@router.get("/sessions/{session_id}/turns/{turn_id}/audio")
def get_turn_audio(session_id: str, turn_id: str, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    s = _visible_session(db, user, session_id)
    turn = db.get(Turn, turn_id)
    if turn is None or turn.session_id != s.id or not turn.audio_path:
        raise not_found("Ses")
    media_root = get_settings().media_dir.resolve()
    path = (media_root / turn.audio_path).resolve()
    if not path.is_relative_to(media_root) or not path.exists():
        raise not_found("Ses")
    # FileResponse Range isteklerini (206) destekler.
    return FileResponse(path, media_type=turn.audio_mime or "application/octet-stream",
                        headers={"Cache-Control": "private, max-age=3600"})


@router.post("/sessions/{session_id}/finish", status_code=202)
def finish_session(session_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = _own_session(db, user, session_id)
    ev = db.get(Evaluation, s.id)
    if ev:  # idempotent
        return {"session_id": s.id, "evaluation_job_id": ev.job_id}
    if _active_job(db, s.id):
        raise conflict("turn_in_progress", "Son cevabınız işlenirken görüşme bitirilemez.")
    if db.query(Turn).filter_by(session_id=s.id, speaker="employee", status="ready").count() == 0:
        raise conflict("conflict", "Değerlendirme için en az bir cevap vermelisiniz.")

    s.status, s.finished_at = "finished", utcnow()
    job = Job(org_id=s.org_id, owner_id=user.id, kind="evaluation", priority=10, session_id=s.id)
    db.add(job)
    db.flush()
    db.add(Evaluation(session_id=s.id, job_id=job.id))
    if s.assignment_id:
        a = db.get(Assignment, s.assignment_id)
        a.status, a.completed_session_id = "completed", s.id
    db.commit()
    return {"session_id": s.id, "evaluation_job_id": job.id}


@router.get("/sessions/{session_id}/evaluation")
def get_evaluation(session_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = _visible_session(db, user, session_id)
    ev = db.get(Evaluation, s.id)
    if ev is None:
        raise conflict("evaluation_not_ready", "Görüşme henüz bitirilmedi.")
    report = None
    if ev.report is not None:
        t = db.get(Training, s.training_id)
        latest = schemas.latest_review(db, s.id)
        report = evalsvc.apply_review(ev.report, schemas.review_json(db, latest) if latest else None, t.rubric)
    return {"session_id": s.id, "status": ev.status, "evaluation_job_id": ev.job_id,
            "report": report, "error": ev.error if ev.status == "error" else None}

