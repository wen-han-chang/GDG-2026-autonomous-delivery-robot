"""add avatar to users

Revision ID: b1c2d3e4f5a6
Revises: 04adb7ffa8e1
Create Date: 2026-04-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'b1c2d3e4f5a6'
down_revision = '04adb7ffa8e1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('avatar', sa.String(), nullable=True))


def downgrade():
    op.drop_column('users', 'avatar')
