"""add remote recipe image fields

Revision ID: 9f5ab6c1d2b4
Revises: 32adc4af25e2
Create Date: 2026-03-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9f5ab6c1d2b4"
down_revision = "32adc4af25e2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("recipes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("image_storage_key", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("image_url", sa.String(length=500), nullable=True))


def downgrade():
    with op.batch_alter_table("recipes", schema=None) as batch_op:
        batch_op.drop_column("image_url")
        batch_op.drop_column("image_storage_key")
