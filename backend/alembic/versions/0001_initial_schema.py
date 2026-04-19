"""Initial schema — users, learner_states, sessions, quizzes, resources.

Revision ID: 0001
Revises: 
Create Date: 2026-04-19
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "learner_states",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("cls_json", JSONB, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table(
        "sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent", sa.String(50), nullable=False),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("ended_at", sa.DateTime, nullable=True),
        sa.Column("messages_json", JSONB, nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "quizzes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week_number", sa.Integer, nullable=False),
        sa.Column("questions_json", JSONB, nullable=False),
        sa.Column("submitted_at", sa.DateTime, nullable=True),
        sa.Column("scores_json", JSONB, nullable=True),
    )
    op.create_index("ix_quizzes_user_id", "quizzes", ["user_id"])

    op.create_table(
        "resources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("topic", sa.String(255), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("embedding_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_resources_topic", "resources", ["topic"])


def downgrade() -> None:
    op.drop_table("resources")
    op.drop_table("quizzes")
    op.drop_table("sessions")
    op.drop_table("learner_states")
    op.drop_table("users")
