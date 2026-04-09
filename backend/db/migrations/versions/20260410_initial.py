"""initial

Revision ID: 20260410_initial
Revises: None
Create Date: 2026-04-10 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260410_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", sa.Text(), nullable=False, unique=True),
        sa.Column("session_type", sa.Text()),
        sa.Column("circuit", sa.Text()),
        sa.Column("car_model", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "laps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", sa.Text(), sa.ForeignKey("sessions.session_id"), nullable=False),
        sa.Column("lap_number", sa.Integer(), nullable=False),
        sa.Column("lap_time_ms", sa.Integer()),
        sa.Column("is_valid", sa.Boolean()),
        sa.Column("circuit", sa.Text()),
        sa.Column("car_model", sa.Text()),
        sa.Column("recorded_at", sa.DateTime(timezone=True)),
        sa.Column("summary", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("session_id", "lap_number"),
    )
    op.create_index("idx_laps_session", "laps", ["session_id"])
    op.create_index("idx_laps_circuit_car", "laps", ["circuit", "car_model"])

    op.create_table(
        "analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", sa.Text(), sa.ForeignKey("sessions.session_id"), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column("model_used", sa.Text()),
        sa.Column("prompt_tokens", sa.Integer()),
        sa.Column("completion_tokens", sa.Integer()),
    )
    op.create_index("idx_analyses_session", "analyses", ["session_id"])

    op.create_table(
        "reference_laps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("circuit", sa.Text(), nullable=False),
        sa.Column("car_model", sa.Text(), nullable=False),
        sa.Column("lap_time_ms", sa.Integer()),
        sa.Column("source", sa.Text()),
        sa.Column("summary", postgresql.JSONB(), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("reference_laps")
    op.drop_index("idx_analyses_session", table_name="analyses")
    op.drop_table("analyses")
    op.drop_index("idx_laps_circuit_car", table_name="laps")
    op.drop_index("idx_laps_session", table_name="laps")
    op.drop_table("laps")
    op.drop_table("sessions")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
