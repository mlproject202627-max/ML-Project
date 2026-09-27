"""Banking platform + telemetry tables.

These tables previously existed only via `Base.metadata.create_all()` at
application startup, which meant `alembic upgrade head` could not build a
working database from scratch. This revision closes that gap.

Revision ID: 003_banking_tables
Revises: 002_employee_fields
Create Date: 2026-09-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003_banking_tables"
down_revision: Union[str, None] = "002_employee_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── branches ───────────────────────────────────────────────────────────
    op.create_table(
        "branches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("ifsc", sa.String(11), nullable=False),
        sa.Column("address", sa.String(255)),
        sa.Column("city", sa.String(80)),
        sa.Column("state", sa.String(80)),
        sa.Column("phone", sa.String(32)),
        sa.Column("manager_name", sa.String(120)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_branches_code", "branches", ["code"])

    # ── customers ──────────────────────────────────────────────────────────
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", sa.String(24), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("email", sa.String(160)),
        sa.Column("phone", sa.String(24)),
        sa.Column("pan", sa.String(10)),
        sa.Column("aadhaar_masked", sa.String(12)),
        sa.Column("dob", sa.String(10)),
        sa.Column("address", sa.String(255)),
        sa.Column("city", sa.String(80)),
        sa.Column("state", sa.String(80)),
        sa.Column("segment", sa.String(40)),
        sa.Column("risk_rating", sa.String(12)),
        sa.Column("kyc_status", sa.String(20)),
        sa.Column("kyc_expiry", sa.DateTime(timezone=True)),
        sa.Column("relationship_manager", sa.String(120)),
        sa.Column("home_branch_code", sa.String(32), sa.ForeignKey("branches.code")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_customers_customer_id", "customers", ["customer_id"])
    op.create_index("ix_customers_name", "customers", ["name"])

    # ── accounts ───────────────────────────────────────────────────────────
    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("account_number", sa.String(20), nullable=False, unique=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("account_type", sa.String(24), nullable=False),
        sa.Column("scheme", sa.String(60)),
        sa.Column("balance", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_txn_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_accounts_account_number", "accounts", ["account_number"])
    op.create_index("ix_accounts_customer_id", "accounts", ["customer_id"])

    # ── transactions ───────────────────────────────────────────────────────
    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("txn_id", sa.String(24), nullable=False, unique=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("direction", sa.String(6), nullable=False),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("channel", sa.String(24), nullable=False),
        sa.Column("category", sa.String(40)),
        sa.Column("narration", sa.String(200)),
        sa.Column("counterparty", sa.String(160)),
        sa.Column("counterparty_account", sa.String(20)),
        sa.Column("balance_after", sa.Numeric(16, 2)),
        sa.Column("status", sa.String(12), nullable=False, server_default="SUCCESS"),
        sa.Column("reference", sa.String(64)),
    )
    op.create_index("ix_transactions_txn_id", "transactions", ["txn_id"])
    op.create_index("ix_transactions_account_id", "transactions", ["account_id"])
    op.create_index("ix_transactions_posted_at", "transactions", ["posted_at"])

    # ── loan_applications ──────────────────────────────────────────────────
    op.create_table(
        "loan_applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("loan_id", sa.String(24), nullable=False, unique=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("product", sa.String(40), nullable=False),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("tenure_months", sa.Integer, nullable=False),
        sa.Column("interest_rate", sa.Numeric(5, 2)),
        sa.Column("emi", sa.Numeric(14, 2)),
        sa.Column("purpose", sa.String(255)),
        sa.Column("status", sa.String(20), nullable=False, server_default="SUBMITTED"),
        sa.Column("stage", sa.String(40)),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("branch_code", sa.String(32), sa.ForeignKey("branches.code")),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("remarks", sa.Text),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_loan_applications_loan_id", "loan_applications", ["loan_id"])
    op.create_index("ix_loan_applications_customer_id", "loan_applications", ["customer_id"])

    # ── kyc_cases ──────────────────────────────────────────────────────────
    op.create_table(
        "kyc_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_number", sa.String(24), nullable=False, unique=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("case_type", sa.String(20), nullable=False, server_default="PERIODIC"),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("priority", sa.String(12), nullable=False, server_default="MEDIUM"),
        sa.Column("documents_pending", postgresql.JSON, server_default="[]"),
        sa.Column("risk_rating", sa.String(12)),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_kyc_cases_case_number", "kyc_cases", ["case_number"])
    op.create_index("ix_kyc_cases_customer_id", "kyc_cases", ["customer_id"])

    # ── portal_documents ───────────────────────────────────────────────────
    op.create_table(
        "portal_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("doc_id", sa.String(24), nullable=False, unique=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id")),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("doc_type", sa.String(40)),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_size", sa.Integer),
        sa.Column("mime", sa.String(80)),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("status", sa.String(16), nullable=False, server_default="UPLOADED"),
        sa.Column("branch_code", sa.String(32), sa.ForeignKey("branches.code")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_portal_documents_doc_id", "portal_documents", ["doc_id"])
    op.create_index("ix_portal_documents_customer_id", "portal_documents", ["customer_id"])

    # ── support_tickets ────────────────────────────────────────────────────
    op.create_table(
        "support_tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticket_number", sa.String(24), nullable=False, unique=True),
        sa.Column("raised_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("priority", sa.String(12), nullable=False, server_default="MEDIUM"),
        sa.Column("status", sa.String(16), nullable=False, server_default="OPEN"),
        sa.Column("assignee_name", sa.String(120)),
        sa.Column("resolution", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_support_tickets_ticket_number", "support_tickets", ["ticket_number"])
    op.create_index("ix_support_tickets_raised_by", "support_tickets", ["raised_by"])

    # ── portal_notifications ───────────────────────────────────────────────
    op.create_table(
        "portal_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(24), nullable=False, server_default="GENERAL"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text),
        sa.Column("link", sa.String(120)),
        sa.Column("read", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_portal_notifications_user_id", "portal_notifications", ["user_id"])
    op.create_index("ix_portal_notifications_created_at", "portal_notifications", ["created_at"])

    # ── telemetry_events ───────────────────────────────────────────────────
    op.create_table(
        "telemetry_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default="browser"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("location", sa.String(255)),
        sa.Column("latitude", sa.String(32)),
        sa.Column("longitude", sa.String(32)),
        sa.Column("accuracy_m", sa.Float),
        sa.Column("device", sa.String(255)),
        sa.Column("resource", sa.String(512)),
        sa.Column("application", sa.String(255)),
        sa.Column("metadata", postgresql.JSON, server_default="{}"),
        sa.Column("risk_contribution", sa.Float, server_default="0.0"),
    )
    op.create_index("ix_telemetry_events_user_id", "telemetry_events", ["user_id"])
    op.create_index("ix_telemetry_events_event_type", "telemetry_events", ["event_type"])
    op.create_index("ix_telemetry_events_occurred_at", "telemetry_events", ["occurred_at"])
    op.create_index("idx_telemetry_user_time", "telemetry_events", ["user_id", "occurred_at"])
    op.create_index("idx_telemetry_type", "telemetry_events", ["event_type"])

    # ── user_sessions ──────────────────────────────────────────────────────
    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_token", sa.String(255), nullable=False, unique=True),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.String(512)),
        sa.Column("location", sa.String(255)),
        sa.Column("latitude", sa.String(32)),
        sa.Column("longitude", sa.String(32)),
        sa.Column("logged_in_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("logged_out_at", sa.DateTime(timezone=True)),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_session_token", "user_sessions", ["session_token"])
    op.create_index("idx_user_sessions_user_logged_in", "user_sessions", ["user_id", "logged_in_at"])

    # ── agent_keys ─────────────────────────────────────────────────────────
    op.create_table(
        "agent_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("key_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("label", sa.String(255)),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_agent_keys_key_hash", "agent_keys", ["key_hash"])
    op.create_index("ix_agent_keys_user_id", "agent_keys", ["user_id"])
    op.create_index("idx_agent_keys_user", "agent_keys", ["user_id"])


def downgrade() -> None:
    op.drop_table("agent_keys")
    op.drop_table("user_sessions")
    op.drop_table("telemetry_events")
    op.drop_table("portal_notifications")
    op.drop_table("support_tickets")
    op.drop_table("portal_documents")
    op.drop_table("kyc_cases")
    op.drop_table("loan_applications")
    op.drop_table("transactions")
    op.drop_table("accounts")
    op.drop_table("customers")
    op.drop_table("branches")
