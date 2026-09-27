"""Banking portal domain models.

Employees of the bank use the portal to serve customers. Every customer-facing
action (customer search, account view, statement download, transfer, …) is
additionally mirrored as a telemetry/Activity row by the API layer so Sentinel
can monitor behaviour silently — the portal UI itself never shows security
controls to banking staff.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, DateTime, Numeric, ForeignKey, Index, Text, Boolean, JSON, Integer,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


def _now():
    return datetime.now(timezone.utc)


class Branch(Base):
    __tablename__ = "branches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(32), unique=True, nullable=False, index=True)   # VJA-CENTRAL
    name = Column(String(120), nullable=False)
    ifsc = Column(String(11), nullable=False)
    address = Column(String(255))
    city = Column(String(80))
    state = Column(String(80))
    phone = Column(String(32))
    manager_name = Column(String(120))
    created_at = Column(DateTime(timezone=True), default=_now)


class Customer(Base):
    __tablename__ = "customers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(String(24), unique=True, nullable=False, index=True)  # CUST-10021
    name = Column(String(160), nullable=False, index=True)
    email = Column(String(160))
    phone = Column(String(24))
    pan = Column(String(10))               # masked in API responses
    aadhaar_masked = Column(String(12))    # store masked form only
    dob = Column(String(10))               # ISO date
    address = Column(String(255))
    city = Column(String(80))
    state = Column(String(80))
    segment = Column(String(40))           # RETAIL / PREMIUM / BUSINESS / Staff
    risk_rating = Column(String(12))       # LOW / MEDIUM / HIGH
    kyc_status = Column(String(20))        # VERIFIED / PENDING / EXPIRED / REJECTED
    kyc_expiry = Column(DateTime(timezone=True))
    relationship_manager = Column(String(120))
    home_branch_code = Column(String(32), ForeignKey("branches.code"))
    created_at = Column(DateTime(timezone=True), default=_now)

    branch = relationship("Branch", foreign_keys=[home_branch_code])
    accounts = relationship("BankAccount", back_populates="customer")


class BankAccount(Base):
    __tablename__ = "accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_number = Column(String(20), unique=True, nullable=False, index=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True)
    account_type = Column(String(24), nullable=False)   # SAVINGS / CURRENT / SALARY / FD
    scheme = Column(String(60))                          # e.g. "Apna Savings Max"
    balance = Column(Numeric(16, 2), nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="INR")
    status = Column(String(16), nullable=False, default="ACTIVE")  # ACTIVE/DORMANT/FROZEN/CLOSED
    opened_at = Column(DateTime(timezone=True), default=_now)
    last_txn_at = Column(DateTime(timezone=True))

    customer = relationship("Customer", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    txn_id = Column(String(24), unique=True, nullable=False, index=True)  # TXN-88342107
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True)
    posted_at = Column(DateTime(timezone=True), nullable=False, default=_now, index=True)
    direction = Column(String(6), nullable=False)        # DR / CR
    amount = Column(Numeric(16, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    channel = Column(String(24), nullable=False)         # UPI/NEFT/IMPS/ATM/BRANCH/POS/ACH
    category = Column(String(40))                        # SALARY/RENT/GROCERY/…
    narration = Column(String(200))
    counterparty = Column(String(160))
    counterparty_account = Column(String(20))
    balance_after = Column(Numeric(16, 2))
    status = Column(String(12), nullable=False, default="SUCCESS")  # SUCCESS/PENDING/FAILED
    reference = Column(String(64))

    account = relationship("BankAccount", back_populates="transactions")


class LoanApplication(Base):
    __tablename__ = "loan_applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    loan_id = Column(String(24), unique=True, nullable=False, index=True)  # LN-2026-0134
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True)
    product = Column(String(40), nullable=False)    # HOME/AUTO/PERSONAL/GOLD/EDUCATION
    amount = Column(Numeric(16, 2), nullable=False)
    tenure_months = Column(Integer, nullable=False)
    interest_rate = Column(Numeric(5, 2))
    emi = Column(Numeric(14, 2))
    purpose = Column(String(255))
    status = Column(String(20), nullable=False, default="SUBMITTED")
    # SUBMITTED → UNDER_REVIEW → APPROVED / REJECTED / DISBURSED
    stage = Column(String(40))                      # DOC_COLLECTION/CREDIT_CHECK/…
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    branch_code = Column(String(32), ForeignKey("branches.code"))
    decided_at = Column(DateTime(timezone=True))
    remarks = Column(Text)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    customer = relationship("Customer")
    assignee = relationship("User", foreign_keys=[assigned_to])


class KycCase(Base):
    __tablename__ = "kyc_cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_number = Column(String(24), unique=True, nullable=False, index=True)  # KYC-4512
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True)
    case_type = Column(String(20), nullable=False, default="PERIODIC")  # NEW/PERIODIC/UPDATE
    status = Column(String(20), nullable=False, default="PENDING")  # PENDING/IN_REVIEW/VERIFIED/REJECTED/EXPIRED
    priority = Column(String(12), nullable=False, default="MEDIUM")
    documents_pending = Column(JSON, default=list)   # ["PAN","AADHAAR",...]
    risk_rating = Column(String(12))
    due_at = Column(DateTime(timezone=True))
    notes = Column(Text)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    customer = relationship("Customer")
    assignee = relationship("User", foreign_keys=[assigned_to])


class PortalDocument(Base):
    __tablename__ = "portal_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id = Column(String(24), unique=True, nullable=False, index=True)  # DOC-3312
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), index=True)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title = Column(String(160), nullable=False)
    doc_type = Column(String(40))   # ID_PROOF/ADDRESS_PROOF/INCOME_PROOF/FORM_16/STATEMENT/OTHER
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer)          # bytes
    mime = Column(String(80))
    version = Column(Integer, nullable=False, default=1)
    status = Column(String(16), nullable=False, default="UPLOADED")  # UPLOADED/VERIFIED/REJECTED/ARCHIVED
    branch_code = Column(String(32), ForeignKey("branches.code"))
    created_at = Column(DateTime(timezone=True), default=_now)

    customer = relationship("Customer")
    uploader = relationship("User", foreign_keys=[uploaded_by])


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_number = Column(String(24), unique=True, nullable=False, index=True)  # TCK-2091
    raised_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    category = Column(String(40), nullable=False)   # IT/HR/OPERATIONS/COMPLIANCE/OTHER
    subject = Column(String(200), nullable=False)
    description = Column(Text)
    priority = Column(String(12), nullable=False, default="MEDIUM")
    status = Column(String(16), nullable=False, default="OPEN")  # OPEN/IN_PROGRESS/RESOLVED/CLOSED
    assignee_name = Column(String(120))
    resolution = Column(Text)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


class PortalNotification(Base):
    """Employee-facing notifications (bank announcements, txn alerts, task items)."""
    __tablename__ = "portal_notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    category = Column(String(24), nullable=False, default="GENERAL")  # GENERAL/TRANSFERS/LOANS/KYC/SUPPORT
    title = Column(String(200), nullable=False)
    body = Column(Text)
    link = Column(String(120))          # optional in-portal route, e.g. /loans
    read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=_now, index=True)
