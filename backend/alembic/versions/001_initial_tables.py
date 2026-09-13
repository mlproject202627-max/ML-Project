"""Initial tables - users, roles, user_roles, activities, anomalies, risk_events, investigations, investigation_events, detection_policies, notifications

Revision ID: 001_initial
Revises:
Create Date: 2026-09-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── roles ──────────────────────────────────────────────────────────────
    op.create_table(
        'roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('name', sa.String(50), nullable=False, unique=True),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── users ──────────────────────────────────────────────────────────────
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('department', sa.String(100), nullable=True),
        sa.Column('job_title', sa.String(255), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='ACTIVE'),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_users_email', 'users', ['email'])

    # ── user_roles ─────────────────────────────────────────────────────────
    op.create_table(
        'user_roles',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('roles.id'), primary_key=True),
    )

    # ── activities ─────────────────────────────────────────────────────────
    op.create_table(
        'activities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('action', sa.String(255), nullable=False),
        sa.Column('resource', sa.String(255), nullable=True),
        sa.Column('source_ip', sa.String(45), nullable=True),
        sa.Column('device', sa.String(255), nullable=True),
        sa.Column('location', sa.String(255), nullable=True),
        sa.Column('application', sa.String(255), nullable=True),
        sa.Column('metadata', postgresql.JSON, nullable=True, server_default='{}'),
        sa.Column('risk_contribution', sa.Float, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_activities_user_id', 'activities', ['user_id'])
    op.create_index('idx_activities_timestamp', 'activities', ['timestamp'])
    op.create_index('idx_activities_event_type', 'activities', ['event_type'])

    # ── anomalies ──────────────────────────────────────────────────────────
    op.create_table(
        'anomalies',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('activity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('activities.id'), nullable=True),
        sa.Column('detection_type', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('risk_score', sa.Float, nullable=False),
        sa.Column('anomaly_score', sa.Float, nullable=False),
        sa.Column('confidence', sa.Float, nullable=False),
        sa.Column('description', sa.String(1000), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='OPEN'),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_anomalies_user_id', 'anomalies', ['user_id'])
    op.create_index('idx_anomalies_severity', 'anomalies', ['severity'])
    op.create_index('idx_anomalies_status', 'anomalies', ['status'])
    op.create_index('idx_anomalies_detected_at', 'anomalies', ['detected_at'])

    # ── risk_events ────────────────────────────────────────────────────────
    op.create_table(
        'risk_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('anomaly_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('anomalies.id'), nullable=True),
        sa.Column('signal_type', sa.String(50), nullable=False),
        sa.Column('signal_value', sa.Float, nullable=False),
        sa.Column('weight', sa.Float, nullable=False),
        sa.Column('contribution', sa.Float, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_risk_events_user_id', 'risk_events', ['user_id'])

    # ── investigations ─────────────────────────────────────────────────────
    op.create_table(
        'investigations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('anomaly_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('anomalies.id'), nullable=False),
        sa.Column('assigned_to', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('summary', sa.Text, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='OPEN'),
        sa.Column('priority', sa.String(20), nullable=False, server_default='MEDIUM'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    )

    # ── investigation_events ───────────────────────────────────────────────
    op.create_table(
        'investigation_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('investigation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('investigations.id'), nullable=False),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── detection_policies ─────────────────────────────────────────────────
    op.create_table(
        'detection_policies',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.String(1000), nullable=True),
        sa.Column('detection_type', sa.String(50), nullable=False),
        sa.Column('enabled', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('severity', sa.String(20), nullable=False, server_default='MEDIUM'),
        sa.Column('threshold', sa.Float, nullable=False, server_default='0.7'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── notifications ──────────────────────────────────────────────────────
    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text, nullable=True),
        sa.Column('related_anomaly_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('anomalies.id'), nullable=True),
        sa.Column('read', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('notifications')
    op.drop_table('detection_policies')
    op.drop_table('investigation_events')
    op.drop_table('investigations')
    op.drop_index('idx_risk_events_user_id', 'risk_events')
    op.drop_table('risk_events')
    op.drop_index('idx_anomalies_detected_at', 'anomalies')
    op.drop_index('idx_anomalies_status', 'anomalies')
    op.drop_index('idx_anomalies_severity', 'anomalies')
    op.drop_index('idx_anomalies_user_id', 'anomalies')
    op.drop_table('anomalies')
    op.drop_index('idx_activities_event_type', 'activities')
    op.drop_index('idx_activities_timestamp', 'activities')
    op.drop_index('idx_activities_user_id', 'activities')
    op.drop_table('activities')
    op.drop_table('user_roles')
    op.drop_index('ix_users_email', 'users')
    op.drop_table('users')
    op.drop_table('roles')
