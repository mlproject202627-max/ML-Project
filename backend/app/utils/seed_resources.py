"""Seed the classified sensitive-resource registry (spec §5).

Idempotent: existing `resource_id` rows are updated in place, so the seed can
run on every startup without duplicating the registry.

Everything here is synthetic. Customer names come from the demo banking seed;
no real person's data appears anywhere in this file.

Classification ladder and who may touch what:

    PUBLIC               brochures, rate cards          — everyone
    INTERNAL             circulars, branch reports      — all staff
    CONFIDENTIAL         statements, loan files         — branch + product roles
    HIGHLY_CONFIDENTIAL  KYC packets, audit findings    — compliance + managers
    RESTRICTED           PII exports, AML reports       — compliance only

The registry is what makes "not every employee can access everything" true in
practice: `Resource.allows()` is consulted on every access, and the API refuses
with 403 rather than relying on the UI to hide a link.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.banking import Branch, Customer
from app.models.resource import Resource

logger = logging.getLogger("sentinel.seed.resources")

#: Role sets reused across many resources.
ALL_STAFF = "TELLER,RELATIONSHIP_MANAGER,BRANCH_MANAGER,COMPLIANCE_OFFICER,OPERATIONS_MANAGER"
CUSTOMER_FACING = "TELLER,RELATIONSHIP_MANAGER,BRANCH_MANAGER"
LENDING = "RELATIONSHIP_MANAGER,BRANCH_MANAGER"
COMPLIANCE_ONLY = "COMPLIANCE_OFFICER"
MANAGEMENT = "BRANCH_MANAGER,COMPLIANCE_OFFICER,OPERATIONS_MANAGER"


def _add(db: Session, **kwargs) -> None:
    """Insert or update one resource, keyed on `resource_id`."""
    resource_id = kwargs["resource_id"]
    existing = db.query(Resource).filter(Resource.resource_id == resource_id).first()
    if existing:
        for key, value in kwargs.items():
            setattr(existing, key, value)
        return
    db.add(Resource(**kwargs))


def seed(db: Session | None = None) -> int:
    """Create/refresh the registry. Returns the number of resources present."""
    owns_session = db is None
    db = db or SessionLocal()
    try:
        if db.query(Branch).count() == 0:
            logger.info("No branches seeded yet; skipping resource registry.")
            return 0

        branches = db.query(Branch).all()
        customers = db.query(Customer).order_by(Customer.customer_id).all()
        now = datetime.now(timezone.utc)

        # ── PUBLIC: no restriction, present so the ladder has a floor ──────
        _add(
            db,
            resource_id="RES-PUB-0001",
            name="Retail Product Rate Card",
            resource_type="MARKETING",
            classification="PUBLIC",
            owner="Product Team",
            owner_department="Retail Banking",
            file_name="rate_card_2026.pdf",
            file_size=248_000,
            mime="application/pdf",
            allowed_roles="",
            allowed_departments="",
            downloadable=True,
            created_at=now,
        )
        _add(
            db,
            resource_id="RES-PUB-0002",
            name="Branch Holiday Calendar",
            resource_type="NOTICE",
            classification="PUBLIC",
            owner="Operations",
            owner_department="Operations",
            file_name="holiday_calendar.pdf",
            file_size=96_500,
            allowed_roles="",
            allowed_departments="",
            downloadable=True,
            created_at=now,
        )

        # ── INTERNAL: every employee, nothing customer-specific ───────────
        _add(
            db,
            resource_id="RES-INT-0001",
            name="Employee Directory (Sentinel Bank)",
            resource_type="DIRECTORY",
            classification="INTERNAL",
            owner="Human Resources",
            owner_department="Operations",
            file_name="employee_directory.pdf",
            file_size=412_000,
            allowed_roles=ALL_STAFF,
            allowed_departments="",
            downloadable=True,
            created_at=now,
        )
        _add(
            db,
            resource_id="RES-INT-0002",
            name="Monthly Branch Performance Summary",
            resource_type="REPORT",
            classification="INTERNAL",
            owner="Branch Operations",
            owner_department="Branch Ops",
            file_name="branch_performance.pdf",
            file_size=880_000,
            allowed_roles=ALL_STAFF,
            allowed_departments="",
            downloadable=True,
            created_at=now,
        )
        _add(
            db,
            resource_id="RES-INT-0003",
            name="RBI Regulatory Circular Digest",
            resource_type="CIRCULAR",
            classification="INTERNAL",
            owner="Compliance",
            owner_department="Compliance",
            file_name="rbi_circular_digest.pdf",
            file_size=655_000,
            allowed_roles=ALL_STAFF,
            allowed_departments="",
            downloadable=True,
            created_at=now,
        )

        # ── CONFIDENTIAL: customer-level operational documents ────────────
        for index, branch in enumerate(branches, start=1):
            _add(
                db,
                resource_id=f"RES-CONF-B{index:02d}",
                name=f"Account Statements Batch — {branch.code}",
                resource_type="STATEMENT",
                classification="CONFIDENTIAL",
                owner=branch.manager_name or "Branch Manager",
                owner_department="Branch Ops",
                file_name=f"statements_{branch.code.lower()}.pdf",
                file_size=1_450_000 + index * 40_000,
                allowed_roles=CUSTOMER_FACING,
                allowed_departments="Branch Ops,Retail Banking",
                downloadable=True,
                created_at=now,
            )
            _add(
                db,
                resource_id=f"RES-CONF-L{index:02d}",
                name=f"Loan Portfolio File — {branch.code}",
                resource_type="LOAN_FILE",
                classification="CONFIDENTIAL",
                owner=branch.manager_name or "Branch Manager",
                owner_department="Retail Banking",
                file_name=f"loan_portfolio_{branch.code.lower()}.pdf",
                file_size=2_100_000 + index * 55_000,
                allowed_roles=LENDING,
                allowed_departments="Retail Banking",
                downloadable=True,
                created_at=now,
            )

        # ── HIGHLY_CONFIDENTIAL: per-customer KYC packets ─────────────────
        kyc_customers = [c for c in customers if c.kyc_status in ("PENDING", "EXPIRED", "VERIFIED")][:12]
        for index, customer in enumerate(kyc_customers, start=1):
            _add(
                db,
                resource_id=f"RES-KYC-{index:04d}",
                name=f"KYC Packet — {customer.name} ({customer.customer_id})",
                resource_type="KYC_DOCUMENT",
                classification="HIGHLY_CONFIDENTIAL",
                owner="Compliance",
                owner_department="Compliance",
                customer_id=customer.id,
                file_name=f"kyc_{customer.customer_id.lower()}.pdf",
                file_size=3_200_000 + index * 21_000,
                allowed_roles="COMPLIANCE_OFFICER,RELATIONSHIP_MANAGER,BRANCH_MANAGER",
                allowed_departments="Compliance,Retail Banking,Branch Ops",
                downloadable=True,
                created_at=now,
            )

        _add(
            db,
            resource_id="RES-AUD-0001",
            name="Internal Audit Findings — Q2 FY26",
            resource_type="AUDIT_REPORT",
            classification="HIGHLY_CONFIDENTIAL",
            owner="Internal Audit",
            owner_department="Compliance",
            file_name="internal_audit_q2fy26.pdf",
            file_size=1_880_000,
            allowed_roles=MANAGEMENT,
            allowed_departments="Compliance,Operations",
            downloadable=True,
            created_at=now,
        )
        _add(
            db,
            resource_id="RES-FRD-0001",
            name="Open Fraud Case Files",
            resource_type="FRAUD_CASE_FILE",
            classification="HIGHLY_CONFIDENTIAL",
            owner="Fraud Investigation Unit",
            owner_department="Compliance",
            file_name="fraud_cases_open.pdf",
            file_size=2_640_000,
            allowed_roles=COMPLIANCE_ONLY,
            allowed_departments="Compliance",
            downloadable=True,
            created_at=now,
        )

        # ── RESTRICTED: the crown jewels ──────────────────────────────────
        _add(
            db,
            resource_id="RES-RES-0001",
            name="Customer PII Bulk Export (Full Book)",
            resource_type="PII_EXPORT",
            classification="RESTRICTED",
            owner="Data Protection Officer",
            owner_department="Compliance",
            file_name="customer_pii_export.csv",
            file_size=18_400_000,
            mime="text/csv",
            allowed_roles=COMPLIANCE_ONLY,
            allowed_departments="Compliance",
            downloadable=True,
            created_at=now,
        )
        _add(
            db,
            resource_id="RES-RES-0002",
            name="Suspicious Activity Reports (AML/FIU-IND)",
            resource_type="AML_REPORT",
            classification="RESTRICTED",
            owner="Principal Officer, AML",
            owner_department="Compliance",
            file_name="sar_fiu_ind.pdf",
            file_size=4_120_000,
            allowed_roles=COMPLIANCE_ONLY,
            allowed_departments="Compliance",
            downloadable=True,
            created_at=now,
        )
        _add(
            db,
            resource_id="RES-RES-0003",
            name="High Net-Worth Customer Register",
            resource_type="CUSTOMER_REGISTER",
            classification="RESTRICTED",
            owner="Wealth Management",
            owner_department="Retail Banking",
            file_name="hnw_register.pdf",
            file_size=3_560_000,
            allowed_roles="BRANCH_MANAGER,COMPLIANCE_OFFICER",
            allowed_departments="Compliance,Retail Banking",
            downloadable=True,
            created_at=now,
        )

        # ── Non-downloadable reference material (view-only) ───────────────
        _add(
            db,
            resource_id="RES-INT-0004",
            name="Transaction Monitoring Rulebook",
            resource_type="PROCEDURE",
            classification="INTERNAL",
            owner="Operations",
            owner_department="Operations",
            file_name="txn_monitoring_rulebook.pdf",
            file_size=1_020_000,
            allowed_roles=ALL_STAFF,
            allowed_departments="",
            downloadable=False,
            created_at=now,
        )
        _add(
            db,
            resource_id="RES-CONF-P01",
            name="Pending Approval Queue — High Value Transfers",
            resource_type="APPROVAL_QUEUE",
            classification="CONFIDENTIAL",
            owner="Operations",
            owner_department="Operations",
            file_name="approval_queue.pdf",
            file_size=540_000,
            allowed_roles="BRANCH_MANAGER,OPERATIONS_MANAGER",
            allowed_departments="Operations,Branch Ops",
            downloadable=False,
            created_at=now,
        )

        db.commit()

        total = db.query(Resource).count()
        by_class: dict[str, int] = {}
        for row in db.query(Resource).all():
            by_class[row.classification] = by_class.get(row.classification, 0) + 1
        logger.info("Resource registry ready: %d resources %s", total, by_class)
        return total
    finally:
        if owns_session:
            db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed()
