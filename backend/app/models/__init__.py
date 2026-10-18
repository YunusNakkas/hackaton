"""Veritabanı tabloları. Her satır bir organizasyona aittir; sahiplik backend'de kontrol edilir."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id, utcnow
from app.db import Base


def _id() -> Mapped[str]:
    return mapped_column(String(26), primary_key=True, default=new_id)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=utcnow)


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = _id()
    name: Mapped[str] = mapped_column(String(120))


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = _id()
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(16))  # employee | manager
    password_hash: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = _created()


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = _created()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Training(Base):
    """Yayımlanmış, değişmez eğitim. Yeni sürüm yeni satırdır; oturumlar sürümü sabitler."""

    __tablename__ = "trainings"
    id: Mapped[str] = _id()
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    sector: Mapped[str] = mapped_column(String(32))
    language: Mapped[str] = mapped_column(String(8), default="tr")
    difficulty: Mapped[str] = mapped_column(String(8))
    summary: Mapped[str] = mapped_column(Text)
    estimated_minutes: Mapped[int] = mapped_column(Integer)
    max_turns: Mapped[int] = mapped_column(Integer)
    scenario: Mapped[dict[str, Any]] = mapped_column(JSON)  # ScenarioDraft şekli
    policies: Mapped[list[dict[str, Any]]] = mapped_column(JSON)  # PolicyItem listesi
    rubric: Mapped[dict[str, Any]] = mapped_column(JSON)  # {dimensions: [RubricDimension]}
    scenario_version: Mapped[str] = mapped_column(String(80))
    policy_version: Mapped[str] = mapped_column(String(80))
    rubric_version: Mapped[str] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = _created()


class Assignment(Base):
    __tablename__ = "assignments"
    id: Mapped[str] = _id()
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    training_id: Mapped[str] = mapped_column(ForeignKey("trainings.id"))
    employee_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    assigned_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(16), default="assigned")
    channel: Mapped[str] = mapped_column(String(16), default="message")  # message | phone
    assigned_at: Mapped[datetime] = _created()
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_session_id: Mapped[str | None] = mapped_column(String(26))


class PracticeSession(Base):
    __tablename__ = "practice_sessions"
    __table_args__ = (UniqueConstraint("employee_id", "client_request_id"),)
    id: Mapped[str] = _id()
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    training_id: Mapped[str] = mapped_column(ForeignKey("trainings.id"))
    employee_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    assignment_id: Mapped[str | None] = mapped_column(ForeignKey("assignments.id"))
    channel: Mapped[str] = mapped_column(String(16), default="message")  # message | phone
    customer_stance: Mapped[str] = mapped_column(String(16), default="normal")  # normal | strict
    client_request_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | finished
    prompt_version: Mapped[str] = mapped_column(String(40))
    started_at: Mapped[datetime] = _created()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # "Tekrar dene": raporu çıkmış önceki oturumun tekrarı. mode: same | adaptive
    practice_of_session_id: Mapped[str | None] = mapped_column(ForeignKey("practice_sessions.id"))
    practice_mode: Mapped[str | None] = mapped_column(String(16))
    practice_focus: Mapped[list[str] | None] = mapped_column(JSON)


class Turn(Base):
    __tablename__ = "turns"
    __table_args__ = (UniqueConstraint("session_id", "index"),)
    id: Mapped[str] = _id()
    session_id: Mapped[str] = mapped_column(ForeignKey("practice_sessions.id"), index=True)
    index: Mapped[int] = mapped_column(Integer)
    speaker: Mapped[str] = mapped_column(String(16))  # employee | customer
    status: Mapped[str] = mapped_column(String(16), default="processing")
    text: Mapped[str | None] = mapped_column(Text)
    audio_path: Mapped[str | None] = mapped_column(String(300))  # media_dir'e göre göreli
    audio_mime: Mapped[str | None] = mapped_column(String(40))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = _created()


class Job(Base):
    """Kalıcı iş kuyruğu. Küçük `priority` önce işlenir."""

    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("session_id", "client_request_id"),)
    id: Mapped[str] = _id()
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("practice_sessions.id"))
    turn_id: Mapped[str | None] = mapped_column(ForeignKey("turns.id"))
    client_request_id: Mapped[str | None] = mapped_column(String(36))
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # ara sonuçlar (tekrar denemede atlanır)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Evaluation(Base):
    __tablename__ = "evaluations"
    session_id: Mapped[str] = mapped_column(ForeignKey("practice_sessions.id"), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    report: Mapped[dict[str, Any] | None] = mapped_column(JSON)  # manager_review/effective_total hariç
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = _created()


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[str] = _id()
    session_id: Mapped[str] = mapped_column(ForeignKey("practice_sessions.id"), index=True)
    reviewer_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(16))
    adjustments: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = _created()


class TrainingDraft(Base):
    """Yöneticinin formundan Gemma ile üretilen, düzenlenip yayımlanan eğitim taslağı."""

    __tablename__ = "training_drafts"
    id: Mapped[str] = _id()
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(16), default="generating")  # generating|ready|error|published
    version: Mapped[int] = mapped_column(Integer, default=1)
    form: Mapped[dict[str, Any]] = mapped_column(JSON)
    content: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    generation_job_id: Mapped[str | None] = mapped_column(String(26))
    published_training_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
