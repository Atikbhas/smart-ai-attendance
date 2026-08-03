"""add face encoding metadata

Revision ID: 20260723_0001
Revises: None
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa

revision = "20260723_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("face_encodings") as batch_op:
        batch_op.add_column(sa.Column("image_path", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("confidence_threshold", sa.Float(), nullable=False, server_default="0.6"))


def downgrade():
    with op.batch_alter_table("face_encodings") as batch_op:
        batch_op.drop_column("confidence_threshold")
        batch_op.drop_column("image_path")
