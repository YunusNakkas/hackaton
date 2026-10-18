"""Require temporary employee passwords to be changed on first login."""
from alembic import op
import sqlalchemy as sa

revision = "b2d8e1f07a93"
down_revision = "a8c3d1e55b02"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()))
    # Önceki sürümde çalışan şifrelerini yalnız yöneticiler belirliyordu.
    op.execute("UPDATE users SET must_change_password = 1 WHERE role = 'employee'")


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_column("must_change_password")
