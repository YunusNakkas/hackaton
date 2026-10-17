from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.core.errors import not_found
from app.core.security import current_user
from app.db import get_db
from app.models import Assignment, Training, User
from app.services.prompts import CUSTOMER_VERSION

router = APIRouter(tags=["employee"])


@router.get("/trainings")
def list_trainings(
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    sector: str | None = Query(None, pattern=r"^[a-z][a-z0-9_]{1,31}$"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Training).where(Training.org_id == user.org_id, Training.active.is_(True))
    if sector:
        stmt = stmt.where(Training.sector == sector)
    rows, nxt = schemas.paginate(db, stmt, Training.id, cursor, limit, desc=False)
    return {"items": [schemas.training_summary(r[0]) for r in rows], "next_cursor": nxt}


@router.get("/trainings/{training_id}")
def get_training(training_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = db.get(Training, training_id)
    if t is None or t.org_id != user.org_id or not t.active:
        raise not_found("Eğitim")
    return schemas.training_detail(t, CUSTOMER_VERSION)


@router.get("/assignments")
def list_my_assignments(
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    status: Literal["assigned", "in_progress", "completed"] | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Assignment).where(Assignment.employee_id == user.id)
    if status:
        stmt = stmt.where(Assignment.status == status)
    rows, nxt = schemas.paginate(db, stmt, Assignment.id, cursor, limit, desc=True)
    items = [schemas.assignment_json(r[0], db.get(Training, r[0].training_id)) for r in rows]
    return {"items": items, "next_cursor": nxt}
