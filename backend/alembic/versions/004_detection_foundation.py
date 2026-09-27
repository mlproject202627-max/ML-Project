"""Detection foundation: resources, devices, USB, baselines, risk scores,
audit log, admin actions — plus the telemetry columns and alert lifecycle
fields the detection engine and admin portal depend on.

Revision ID: 004_detection_foundation
Revises: 003_banking_tables
Create Date: 2026-09-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004_detection_foundation"
down_revision: Union[str, None] = "003_banking_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── resources (classified sensitive assets) ────────────────────────────
    op.create_table(
        "resources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("resource_id", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("resource_type", sa.String(40), nullable=False),
        sa.Column("classification", sa.String(24), nullable=False, server_default="INTERNAL"),
        sa.Column("owner", sa.String(160)),
        sa.Column("owner_department", sa.String(80)),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id")),
        sa.Column("file_name", sa.String(255)),
        sa.Column("file_size", sa.Integer),
        sa.Column("mime", sa.String(80), server_default="application/pdf"),
        sa.Column("allowed_roles", sa.String(500), server_default=""),
        sa.Column("allowed_departments", sa.String(500), server_default=""),
        sa.Column("downloadable", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_resources_resource_id", "resources", ["resource_id"])
    op.create_index("ix_resources_classification", "resources", ["classification"])
    op.create_index("idx_resources_classification", "resources", ["classification"])
    op.create_index("idx_resources_type", "resources", ["resource_type"])
    op.create_index("ix_resources_customer_id", "resources", ["customer_id"])

    # ── devices ────────────────────────────────────────────────────────────
    op.create_table(
        "devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("device_id", sa.String(40), nullable=False, unique=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("label", sa.String(120)),
        sa.Column("device_type", sa.String(24), server_default="WORKSTATION"),
        sa.Column("operating_system", sa.String(80)),
        sa.Column("browser", sa.String(80)),
        sa.Column("fingerprint", sa.String(64)),
        sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("seen_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_trusted", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_new", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_devices_device_id", "devices", ["device_id"])
    op.create_index("ix_devices_employee_id", "devices", ["employee_id"])
    op.create_index("ix_devices_fingerprint", "devices", ["fingerprint"])
    op.create_index("idx_devices_employee", "devices", ["employee_id"])
    op.create_index("idx_devices_fingerprint_employee", "devices", ["employee_id", "fingerprint"])

    # ── usb_events (simulated) ─────────────────────────────────────────────
    op.create_table(
        "usb_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("device_label", sa.String(80), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("file_name", sa.String(255)),
        sa.Column("file_size", sa.Integer),
        sa.Column("classification", sa.String(24)),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("resources.id")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_usb_events_employee_id", "usb_events", ["employee_id"])
    op.create_index("ix_usb_events_device_label", "usb_events", ["device_label"])
    op.create_index("ix_usb_events_action", "usb_events", ["action"])
    op.create_index("ix_usb_events_occurred_at", "usb_events", ["occurred_at"])
    op.create_index("ix_usb_events_resource_id", "usb_events", ["resource_id"])
    op.create_index("idx_usb_events_employee_time", "usb_events", ["employee_id", "occurred_at"])
    op.create_index("idx_usb_events_action", "usb_events", ["action"])

    # ── employee_baselines ─────────────────────────────────────────────────
    op.create_table(
        "employee_baselines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("avg_login_hour", sa.Float, server_default="9.0"),
        sa.Column("login_hour_stddev", sa.Float, server_default="1.0"),
        sa.Column("work_start_hour", sa.Float, server_default="9.0"),
        sa.Column("work_end_hour", sa.Float, server_default="18.0"),
        sa.Column("avg_daily_accesses", sa.Float, server_default="0.0"),
        sa.Column("avg_sensitive_accesses", sa.Float, server_default="0.0"),
        sa.Column("avg_downloads", sa.Float, server_default="0.0"),
        sa.Column("avg_customer_searches", sa.Float, server_default="0.0"),
        sa.Column("avg_unique_customers", sa.Float, server_default="0.0"),
        sa.Column("avg_unique_resources", sa.Float, server_default="0.0"),
        sa.Column("typical_session_minutes", sa.Float, server_default="0.0"),
        sa.Column("normal_locations", postgresql.JSON, server_default="{}"),
        sa.Column("normal_countries", postgresql.JSON, server_default="{}"),
        sa.Column("normal_devices", postgresql.JSON, server_default="{}"),
        sa.Column("typical_departments", postgresql.JSON, server_default="{}"),
        sa.Column("observed_days", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sample_events", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("notes", sa.String(500)),
    )
    op.create_index("ix_employee_baselines_employee_id", "employee_baselines", ["employee_id"], unique=True)
    op.create_index("idx_baselines_employee", "employee_baselines", ["employee_id"])

    # ── risk_scores ────────────────────────────────────────────────────────
    op.create_table(
        "risk_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("current_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("previous_score", sa.Float),
        sa.Column("change", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("risk_level", sa.String(16), nullable=False, server_default="LOW"),
        sa.Column("reasons", postgresql.JSON, server_default="[]"),
        sa.Column("rule_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("ml_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("baseline_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("window_start", sa.DateTime(timezone=True)),
        sa.Column("window_end", sa.DateTime(timezone=True)),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("note", sa.Text),
    )
    op.create_index("ix_risk_scores_employee_id", "risk_scores", ["employee_id"])
    op.create_index("ix_risk_scores_current_score", "risk_scores", ["current_score"])
    op.create_index("ix_risk_scores_risk_level", "risk_scores", ["risk_level"])
    op.create_index("ix_risk_scores_timestamp", "risk_scores", ["timestamp"])
    op.create_index("idx_risk_scores_employee_time", "risk_scores", ["employee_id", "timestamp"])
    op.create_index("idx_risk_scores_level", "risk_scores", ["risk_level"])

    # ── audit_logs (append-only) ───────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("actor_code", sa.String(32)),
        sa.Column("actor_type", sa.String(16), nullable=False, server_default="EMPLOYEE"),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("target_type", sa.String(40)),
        sa.Column("target_id", sa.String(64)),
        sa.Column("description", sa.Text),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("request_id", sa.String(64)),
        sa.Column("user_agent", sa.String(256)),
        sa.Column("details", postgresql.JSON, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    # No updated_at column by design: audit rows are never modified.
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_target_id", "audit_logs", ["target_id"])
    op.create_index("ix_audit_logs_request_id", "audit_logs", ["request_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("idx_audit_logs_actor_time", "audit_logs", ["actor_id", "created_at"])
    op.create_index("idx_audit_logs_action", "audit_logs", ["action"])
    op.create_index("idx_audit_logs_target", "audit_logs", ["target_type", "target_id"])

    # ── admin_actions ──────────────────────────────────────────────────────
    op.create_table(
        "admin_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("admin_code", sa.String(32)),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("anomalies.id")),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("note", sa.Text),
        sa.Column("previous_status", sa.String(24)),
        sa.Column("new_status", sa.String(24)),
        sa.Column("details", postgresql.JSON, server_default="{}"),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_admin_actions_admin_id", "admin_actions", ["admin_id"])
    op.create_index("ix_admin_actions_alert_id", "admin_actions", ["alert_id"])
    op.create_index("ix_admin_actions_action", "admin_actions", ["action"])
    op.create_index("ix_admin_actions_created_at", "admin_actions", ["created_at"])
    op.create_index("idx_admin_actions_alert_time", "admin_actions", ["alert_id", "created_at"])
    op.create_index("idx_admin_actions_admin", "admin_actions", ["admin_id"])
    op.create_index("idx_admin_actions_action", "admin_actions", ["action"])

    # ── activities: structured telemetry columns ───────────────────────────
    op.add_column("activities", sa.Column("resource_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("resources.id"), nullable=True))
    op.add_column("activities", sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=True))
    op.add_column("activities", sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id"), nullable=True))
    op.add_column("activities", sa.Column("country", sa.String(80), nullable=True))
    op.add_column("activities", sa.Column("city", sa.String(80), nullable=True))
    op.add_column("activities", sa.Column("sensitivity", sa.String(24), server_default="INTERNAL"))
    op.add_column("activities", sa.Column("severity", sa.String(16), server_default="LOW"))

    op.create_index("idx_activities_user_time", "activities", ["user_id", "timestamp"])
    op.create_index("idx_activities_severity", "activities", ["severity"])
    op.create_index("idx_activities_customer", "activities", ["customer_id"])
    op.create_index("idx_activities_resource", "activities", ["resource_id"])
    op.create_index("idx_activities_device", "activities", ["device_id"])

    # ── anomalies → full alert lifecycle ───────────────────────────────────
    op.add_column("anomalies", sa.Column("title", sa.String(255), nullable=True))
    op.add_column("anomalies", sa.Column("trigger", sa.String(500), nullable=True))
    op.add_column("anomalies", sa.Column("rule_hits", postgresql.JSON, server_default="[]"))
    op.add_column("anomalies", sa.Column("evidence", postgresql.JSON, server_default="{}"))
    op.add_column("anomalies", sa.Column("ml_anomaly_score", sa.Float, nullable=True))
    op.add_column("anomalies", sa.Column("baseline_deviation", sa.Float, nullable=True))
    op.add_column("anomalies", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("anomalies", sa.Column("resolved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("anomalies", sa.Column("resolution_reason", sa.Text, nullable=True))

    op.create_index("idx_anomalies_risk_score", "anomalies", ["risk_score"])
    op.create_index("idx_anomalies_user_status", "anomalies", ["user_id", "status"])

    # Normalise the legacy status vocabulary onto the alert lifecycle so the
    # admin queue's filters work on rows created before this revision.
    op.execute("UPDATE anomalies SET status = 'OPEN' WHERE status IN ('NEW')")
    op.execute("UPDATE anomalies SET status = 'INVESTIGATING' WHERE status IN ('IN_REVIEW', 'ASSIGNED', 'ESCALATED')")
    op.execute("UPDATE anomalies SET status = 'RESOLVED' WHERE status IN ('CONTAINED')")
    op.execute("UPDATE anomalies SET status = 'FALSE_POSITIVE' WHERE status IN ('DISMISSED')")


def downgrade() -> None:
    op.drop_index("idx_anomalies_user_status", table_name="anomalies")
    op.drop_index("idx_anomalies_risk_score", table_name="anomalies")
    for col in ("resolution_reason", "resolved_by", "resolved_at", "baseline_deviation",
                "ml_anomaly_score", "evidence", "rule_hits", "trigger", "title"):
        op.drop_column("anomalies", col)

    for idx in ("idx_activities_device", "idx_activities_resource", "idx_activities_customer",
                "idx_activities_severity", "idx_activities_user_time"):
        op.drop_index(idx, table_name="activities")
    for col in ("severity", "sensitivity", "city", "country", "device_id", "customer_id", "resource_id"):
        op.drop_column("activities", col)

    op.drop_table("admin_actions")
    op.drop_table("audit_logs")
    op.drop_table("risk_scores")
    op.drop_table("employee_baselines")
    op.drop_table("usb_events")
    op.drop_table("devices")
    op.drop_table("resources")
