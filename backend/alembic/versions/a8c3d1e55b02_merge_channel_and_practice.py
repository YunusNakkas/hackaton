"""merge practice channel and practice-again heads

Revision ID: a8c3d1e55b02
Revises: 6f3ce54597fc, c4a1e0b77d21
Create Date: 2026-10-18 02:10:00.000000

"""
from typing import Sequence, Union

revision: str = "a8c3d1e55b02"
down_revision: Union[str, Sequence[str], None] = ("6f3ce54597fc", "c4a1e0b77d21")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
