"""Başlangıç verisi: bir işletme, yönetici + 2 çalışan, mağaza ve otel paketlerinden 6 eğitim.

Kullanım: python -m app.seed   (idempotent; işletme varsa bir şey yapmaz)
Şifre: PM_DEMO_PASSWORD (varsayılan yalnızca dev/test için).
"""

import json
import os
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.db import get_sessionmaker
from app.models import Assignment, Organization, Training, User

DATA = Path(__file__).resolve().parents[2] / "data"
ORG_NAME = "Merkez İşletme"
USERS = [
    ("mehmet@demo.test", "Mehmet Demir", "manager"),
    ("elif@demo.test", "Elif Yılmaz", "employee"),
    ("can@demo.test", "Can Arslan", "employee"),
]


def _load(rel: str) -> dict:
    return json.loads((DATA / rel).read_text(encoding="utf-8"))


def load_trainings(org_id: str) -> list[Training]:
    out = []
    for pack in sorted((DATA / "scenarios").glob("*.json")):
        sc = json.loads(pack.read_text(encoding="utf-8"))
        pol = _load(f"policies/{sc['policy_file']}")
        rub = _load(f"rubrics/{sc['rubric_file']}")
        rubric = {"dimensions": rub["dimensions"]}
        for s in sc["scenarios"]:
            out.append(Training(
                org_id=org_id, title=s["title"], sector=sc["sector"], language="tr",
                difficulty=s["difficulty"], summary=s["summary"],
                estimated_minutes=s["estimated_minutes"], max_turns=s["max_turns"],
                scenario=s, policies=pol["policies"], rubric=rubric,
                scenario_version=f"{sc['version']}#{s['key']}", policy_version=pol["version"],
                rubric_version=rub["version"],
            ))
    return out


def seed(db: Session, password: str, *, require_password_change: bool = False) -> Organization:
    org = db.query(Organization).filter_by(name=ORG_NAME).one_or_none()
    if org is None:
        # Önceki sürümün başlangıç verisini tekrar oluşturmaya çalışmayın.
        org = db.query(Organization).filter_by(name="Demo İşletme").one_or_none()
    if org:
        return org
    org = Organization(name=ORG_NAME)
    db.add(org)
    db.flush()
    pw = hash_password(password)
    users = {email: User(org_id=org.id, email=email, display_name=name, role=role, password_hash=pw,
                         must_change_password=require_password_change and role == "employee")
             for email, name, role in USERS}
    db.add_all(users.values())
    trainings = load_trainings(org.id)
    db.add_all(trainings)
    db.flush()
    first_retail = next(t for t in trainings if t.sector == "retail")
    db.add(Assignment(org_id=org.id, training_id=first_retail.id, employee_id=users["elif@demo.test"].id,
                      assigned_by=users["mehmet@demo.test"].id))
    db.commit()
    return org


def main() -> None:
    settings = get_settings()
    password = os.environ.get("PM_DEMO_PASSWORD")
    if not password:
        if settings.env == "prod":
            raise SystemExit("prod ortamında PM_DEMO_PASSWORD zorunlu")
        password = "prova1234"
    with get_sessionmaker()() as db:
        org = seed(db, password, require_password_change=True)
        n = db.query(Training).filter_by(org_id=org.id).count()
    print(f"seed tamam: {org.name}, {n} eğitim, kullanıcılar: {', '.join(u[0] for u in USERS)}")


if __name__ == "__main__":
    main()
