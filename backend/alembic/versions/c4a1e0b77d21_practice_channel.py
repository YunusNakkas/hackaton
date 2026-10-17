"""practice channel: message or phone

Revision ID: c4a1e0b77d21
Revises: 4429862e877f
Create Date: 2026-10-18 01:45:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4a1e0b77d21"
down_revision: Union[str, Sequence[str], None] = "4429862e877f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("assignments") as batch:
        batch.add_column(sa.Column("channel", sa.String(length=16), nullable=False, server_default="message"))
    with op.batch_alter_table("practice_sessions") as batch:
        batch.add_column(sa.Column("channel", sa.String(length=16), nullable=False, server_default="message"))


def downgrade() -> None:
    with op.batch_alter_table("practice_sessions") as batch:
        batch.drop_column("channel")
    with op.batch_alter_table("assignments") as batch:
        batch.drop_column("channel")
