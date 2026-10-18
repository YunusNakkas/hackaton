"""merge password change and customer stance heads

Revision ID: e7c4b2a91d08
Revises: b2d8e1f07a93, d5f1a8c23e90
Create Date: 2026-10-18 04:30:00.000000

"""
from typing import Sequence, Union

revision: str = "e7c4b2a91d08"
down_revision: Union[str, Sequence[str], None] = ("b2d8e1f07a93", "d5f1a8c23e90")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
