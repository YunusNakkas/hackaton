from app.db import get_sessionmaker
from app.models import Organization, Training, User
from app.seed import seed


def test_seed_cli_accounts_require_first_password_change():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.db import Base

    engine = create_engine("sqlite://")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            seed(db, "temporary-demo-123", require_password_change=True)
            assert all(user.must_change_password for user in db.query(User).filter_by(role="employee").all())
            assert not db.query(User).filter_by(role="manager").one().must_change_password
    finally:
        engine.dispose()


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
