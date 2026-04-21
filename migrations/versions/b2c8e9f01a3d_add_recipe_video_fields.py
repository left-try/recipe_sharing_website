"""add recipe video fields

Revision ID: b2c8e9f01a3d
Revises: 9f5ab6c1d2b4
Create Date: 2026-04-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "b2c8e9f01a3d"
down_revision = "9f5ab6c1d2b4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("recipes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("video_filename", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("video_storage_key", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("video_url", sa.String(length=500), nullable=True))


def downgrade():
    with op.batch_alter_table("recipes", schema=None) as batch_op:
        batch_op.drop_column("video_url")
        batch_op.drop_column("video_storage_key")
        batch_op.drop_column("video_filename")
