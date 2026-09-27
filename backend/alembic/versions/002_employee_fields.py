"""Add employee identity fields to users (banking platform spec §25).

- employee_code: business identifier shown in the UI (e.g. EMP-10452)
- branch_code / branch_name: which branch the employee belongs to
- mfa_enabled: MFA status surfaced on the employee dashboard

Existing rows keep NULL employee_code; the partial unique index only
enforces uniqueness for non-null values.
"""
revision: str = '002_employee_fields'
down_revision: str = '001_initial'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column('users', sa.Column('employee_code', sa.String(32), nullable=True))
    op.add_column('users', sa.Column('branch_code', sa.String(32), nullable=True))
    op.add_column('users', sa.Column('branch_name', sa.String(120), nullable=True))
    op.add_column('users', sa.Column('mfa_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index(
        'ux_users_employee_code', 'users', ['employee_code'],
        unique=True, postgresql_where=sa.text('employee_code IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index('ux_users_employee_code', table_name='users')
    op.drop_column('users', 'mfa_enabled')
    op.drop_column('users', 'branch_name')
    op.drop_column('users', 'branch_code')
    op.drop_column('users', 'employee_code')
