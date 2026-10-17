from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.core.errors import conflict, not_found
from app.core.security import current_user
from app.db import get_db
from app.models import Evaluation, Job, TrainingDraft, Turn, User

router = APIRouter(tags=["jobs"])


def _visible_job(db: Session, user: User, job_id: str) -> Job:
    j = db.get(Job, job_id)
    if j is None or j.org_id != user.org_id or (user.role != "manager" and j.owner_id != user.id):
        raise not_found("İş")
    return j


@router.get("/jobs/{job_id}")
def get_job(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return schemas.job_json(_visible_job(db, user, job_id))


@router.post("/jobs/{job_id}/retry", status_code=202)
def retry_job(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    j = _visible_job(db, user, job_id)
    if j.status == "ready":  # idempotent: zaten bitmiş işi tekrar kuyruğa almayız
        return schemas.job_json(j)
    if j.status != "error" or not (j.error or {}).get("retryable"):
        raise conflict("job_not_retryable", "Bu iş tekrar denenemez.")
    if j.kind == "turn":
        later = db.query(Job).filter(Job.session_id == j.session_id, Job.kind == "turn", Job.id > j.id).first()
        if later:
            raise conflict("job_not_retryable", "Bu cevaptan sonra yeni bir cevap verilmiş.")
        db.get(Turn, j.turn_id).status = "processing"
    if j.kind == "opening":
        db.get(Turn, j.turn_id).status = "processing"
    if j.kind == "evaluation":
        ev = db.get(Evaluation, j.session_id)
        ev.status, ev.error = "pending", None
    if j.kind == "draft_generation":
        db.get(TrainingDraft, j.state["draft_id"]).status = "generating"
    j.status, j.error, j.attempt = "queued", None, j.attempt + 1
    db.commit()
    return schemas.job_json(j)
