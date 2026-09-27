"""Sensitive resource registry with data classification.

Every document, report and dataset an employee can reach is registered here
with a classification level. The classification drives:

- access control (an employee may only reach resources their role/department allows),
- the sensitivity recorded on every telemetry event, and
- the risk contribution when a high-classification resource is touched.

Classification ladder (ascending sensitivity):
    PUBLIC < INTERNAL < CONFIDENTIAL < HIGHLY_CONFIDENTIAL < RESTRICTED
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey, Index, Integer, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


#: Ordered least → most sensitive. Index into this list is the resource's rank.
CLASSIFICATIONS = [
    "PUBLIC",
    "INTERNAL",
    "CONFIDENTIAL",
    "HIGHLY_CONFIDENTIAL",
    "RESTRICTED",
]

#: Risk weight applied when a resource of this classification is accessed.
CLASSIFICATION_RISK_WEIGHT = {
    "PUBLIC": 0.0,
    "INTERNAL": 0.05,
    "CONFIDENTIAL": 0.15,
    "HIGHLY_CONFIDENTIAL": 0.30,
    "RESTRICTED": 0.45,
}

#: Classifications considered "sensitive" for rule and baseline purposes.
SENSITIVE_CLASSIFICATIONS = {"CONFIDENTIAL", "HIGHLY_CONFIDENTIAL", "RESTRICTED"}


def classification_rank(classification: str) -> int:
    """Numeric rank of a classification (0 = PUBLIC). Unknown → INTERNAL rank."""
    try:
        return CLASSIFICATIONS.index((classification or "").upper())
    except ValueError:
        return 1


def is_sensitive(classification: str) -> bool:
    return (classification or "").upper() in SENSITIVE_CLASSIFICATIONS


class Resource(Base):
    """A named, classified thing an employee can access.

    Examples: a customer's KYC bundle, a quarterly fraud report, a compliance
    filing, an internal financial statement, a loan document.
    """

    __tablename__ = "resources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resource_id = Column(String(32), unique=True, nullable=False, index=True)  # RES-0001
    name = Column(String(200), nullable=False)
    resource_type = Column(String(40), nullable=False)   # CUSTOMER_PROFILE / FINANCIAL_STATEMENT / LOAN_DOCUMENT / FRAUD_REPORT / COMPLIANCE_REPORT / RISK_ASSESSMENT / INTERNAL_REPORT / POLICY
    classification = Column(String(24), nullable=False, default="INTERNAL", index=True)
    owner = Column(String(160))                          # owning team or person (business owner)
    owner_department = Column(String(80))                # department(s) allowed by default

    # Optional link to the banking domain when the resource wraps a customer artefact
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True, index=True)

    # Physical-ish attributes (shown in the document browser)
    file_name = Column(String(255))
    file_size = Column(Integer)                          # bytes
    mime = Column(String(80), default="application/pdf")

    # Which roles/departments may reach it. Empty list = any authenticated employee.
    allowed_roles = Column(String(500), default="")      # comma-separated role names
    allowed_departments = Column(String(500), default="")  # comma-separated departments

    downloadable = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    customer = relationship("Customer", foreign_keys=[customer_id])

    __table_args__ = (
        Index("idx_resources_classification", "classification"),
        Index("idx_resources_type", "resource_type"),
    )

    # -- helpers -----------------------------------------------------------

    def role_list(self) -> list[str]:
        return [r.strip() for r in (self.allowed_roles or "").split(",") if r.strip()]

    def department_list(self) -> list[str]:
        return [d.strip() for d in (self.allowed_departments or "").split(",") if d.strip()]

    def allows(self, *, roles: set[str], department: str | None) -> bool:
        """May a user with these roles/department reach this resource?

        An empty allow-list means "no restriction beyond being an employee".
        ADMIN always passes (platform oversight), which is audited separately.
        """
        if "ADMIN" in roles:
            return True
        allowed_roles = set(self.role_list())
        allowed_departments = set(self.department_list())
        if not allowed_roles and not allowed_departments:
            return True
        if allowed_roles & roles:
            return True
        if department and department in allowed_departments:
            return True
        return False
