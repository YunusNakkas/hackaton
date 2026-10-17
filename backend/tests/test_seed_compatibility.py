from app.db import get_sessionmaker
from app.models import Organization, Training, User
from app.seed import seed


def test_seed_reuses_legacy_organization_without_resetting_accounts(env):
    with get_sessionmaker()() as db:
        org = db.query(Organization).one()
        org.name = "Demo İşletme"
        db.commit()
        original_passwords = {u.id: u.password_hash for u in db.query(User).all()}
        original_training_ids = {t.id for t in db.query(Training).all()}

        reused = seed(db, "different-password-123")

        assert reused.id == org.id
        assert db.query(Organization).count() == 1
        assert {u.id: u.password_hash for u in db.query(User).all()} == original_passwords
        assert {t.id for t in db.query(Training).all()} == original_training_ids
