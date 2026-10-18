"""customer stance: normal or strict

Revision ID: d5f1a8c23e90
Revises: a8c3d1e55b02
Create Date: 2026-10-18 04:15:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5f1a8c23e90"
down_revision: Union[str, Sequence[str], None] = "a8c3d1e55b02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("practice_sessions") as batch:
        batch.add_column(sa.Column("customer_stance", sa.String(length=16), nullable=False, server_default="normal"))


def downgrade() -> None:
    with op.batch_alter_table("practice_sessions") as batch:
        batch.drop_column("customer_stance")
