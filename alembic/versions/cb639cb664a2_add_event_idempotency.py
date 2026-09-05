"""add event idempotency key

Revision ID: cb639cb664a2
Revises: 1060ec53e225
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "cb639cb664a2"
down_revision: str | Sequence[str] | None = "1060ec53e225"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
    )
    op.create_unique_constraint(
        "uq_event_project_idempotency_key",
        "events",
        ["project_id", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_event_project_idempotency_key",
        "events",
        type_="unique",
    )
    op.drop_column("events", "idempotency_key")
