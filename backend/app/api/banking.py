"""Banking portal API for bank employees.

Design rules:
- Banking roles (TELLER, RELATIONSHIP_MANAGER, BRANCH_MANAGER, COMPLIANCE_OFFICER,
  OPERATIONS_MANAGER) get customer/account data. ADMIN and security roles may also
  call these endpoints (support/oversight), but the *portal UI* is only shown to
  banking roles.
- Sensitive identifiers (account numbers, PAN, Aadhaar) are always masked in
  responses; full numbers never leave the API.
- Every meaningful read/write is mirrored into TelemetryEvent + Activity rows so
  Sentinel can monitor employee behaviour silently. Failures in monitoring must
  never break the banking operation.
"""
import math
import random
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.activity import Activity
from app.models.telemetry import TelemetryEvent
from app.models.banking import (
    Branch, Customer, BankAccount, Transaction,
    LoanApplication, KycCase, PortalDocument, SupportTicket, PortalNotification,
)

router = APIRouter(prefix="/api/v1/bank", tags=["Banking Portal"])

BANKING_ROLES = {"TELLER", "RELATIONSHIP_MANAGER", "BRANCH_MANAGER", "COMPLIANCE_OFFICER", "OPERATIONS_MANAGER"}

TRANSFERS_ALLOWED = {"TELLER", "RELATIONSHIP_MANAGER", "BRANCH_MANAGER", "OPERATIONS_MANAGER"}
LOANS_ALLOWED = {"RELATIONSHIP_MANAGER", "BRANCH_MANAGER", "OPERATIONS_MANAGER"}
KYC_ALLOWED = {"COMPLIANCE_OFFICER", "BRANCH_MANAGER", "RELATIONSHIP_MANAGER"}
DOCS_ALLOWED = {"TELLER", "RELATIONSHIP_MANAGER", "BRANCH_MANAGER", "COMPLIANCE_OFFICER", "OPERATIONS_MANAGER"}


def roles_of(user: User) -> set:
    return {r.name for r in user.roles}


def require_bank_staff(user: User = Depends(get_current_user)) -> User:
    """The employee portal is for *banking* roles only (spec §3).

    Platform roles are deliberately excluded. "Admins cannot impersonate
    employees" is not a nicety here: an administrator browsing the customer
    book through this router would read real customer records under the
    employee portal's telemetry, which is the exact access pattern this system
    exists to make visible. Separation of duties means the security team
    investigates employee access through `/api/v1/admin/*` — it does not
    perform it.
    """
    if not roles_of(user) & BANKING_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Employee banking portal access requires a banking role",
        )
    return user


def _has(user: User, allowed: set) -> bool:
    return bool(roles_of(user) & allowed)


def _mask_account(number: str) -> str:
    """Show only the last 4 digits: XXXXXX4321."""
    return "X" * max(0, len(number) - 4) + number[-4:]


def _mask_pan(pan: Optional[str]) -> Optional[str]:
    if not pan:
        return None
    return pan[0] + "XXXXX" + pan[-4:] if len(pan) >= 5 else "XXXXX"


def _mirror_telemetry(db: Session, user: User, request: Optional[Request], action: str,
                      resource: str, event_type: str = "DATA_ACCESS", metadata: dict | None = None,
                      customer=None) -> None:
    """Record what the employee did, from Sentinel's point of view.

    Two writes, deliberately:

    1. A `TelemetryEvent` — the original browser-report shape, still served by
       `GET /api/v1/telemetry`.
    2. A security `Activity`, written through `services.telemetry.record_event`,
       which classifies the event, links it to a device/customer/resource,
       checks it against the employee's baseline, and triggers detection.

    Never raises. A monitoring failure must not fail a customer's transfer, so
    the caller's transaction is protected and the event is simply lost.
    """
    try:
        ip = "unknown"
        if request is not None:
            fwd = request.headers.get("x-forwarded-for")
            ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")
        now = datetime.now(timezone.utc)

        db.add(TelemetryEvent(
            user_id=user.id, event_type=event_type, source="browser",
            occurred_at=now, ip_address=ip,
            resource=resource[:512], application="bank-portal",
            event_metadata={"action": action, **(metadata or {})},
        ))
        db.flush()

        from app.services.telemetry import record_event
        record_event(
            db,
            user=user,
            action=action,
            request=request,
            resource_label=resource[:255],
            customer=customer,
            metadata=metadata or {},
        )
    except Exception:
        db.rollback()


def _notify(db: Session, user_id, category: str, title: str, body: str | None = None, link: str | None = None):
    db.add(PortalNotification(user_id=user_id, category=category, title=title, body=body, link=link))


def _gen_txn_id() -> str:
    return f"TXN-{secrets.randbelow(10**8):08d}"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class BankProfileResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    employee_code: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    branch_code: Optional[str] = None
    branch_name: Optional[str] = None
    mfa_enabled: bool = False
    last_login: Optional[datetime] = None
    permissions: List[str] = []

    class Config:
        from_attributes = True


class BranchOut(BaseModel):
    code: str
    name: str
    ifsc: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    phone: Optional[str] = None
    manager_name: Optional[str] = None

    class Config:
        from_attributes = True


class AccountOut(BaseModel):
    id: str
    account_number_masked: str
    account_type: str
    scheme: Optional[str] = None
    balance: float
    currency: str = "INR"
    status: str
    opened_at: datetime
    last_txn_at: Optional[datetime] = None

    @classmethod
    def from_account(cls, a: BankAccount) -> "AccountOut":
        return cls(
            id=str(a.id),
            account_number_masked=_mask_account(a.account_number),
            account_type=a.account_type,
            scheme=a.scheme,
            balance=float(a.balance or 0),
            currency=a.currency,
            status=a.status,
            opened_at=a.opened_at,
            last_txn_at=a.last_txn_at,
        )


class CustomerOut(BaseModel):
    id: str
    customer_id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    pan_masked: Optional[str] = None
    aadhaar_masked: Optional[str] = None
    segment: Optional[str] = None
    risk_rating: Optional[str] = None
    kyc_status: Optional[str] = None
    kyc_expiry: Optional[datetime] = None
    city: Optional[str] = None
    home_branch_code: Optional[str] = None
    relationship_manager: Optional[str] = None
    created_at: datetime

    @classmethod
    def from_customer(cls, c: Customer) -> "CustomerOut":
        return cls(
            id=str(c.id),
            customer_id=c.customer_id,
            name=c.name,
            email=c.email,
            phone=c.phone,
            pan_masked=_mask_pan(c.pan),
            aadhaar_masked=c.aadhaar_masked,
            segment=c.segment,
            risk_rating=c.risk_rating,
            kyc_status=c.kyc_status,
            kyc_expiry=c.kyc_expiry,
            city=c.city,
            home_branch_code=c.home_branch_code,
            relationship_manager=c.relationship_manager,
            created_at=c.created_at,
        )


class CustomerDetailOut(CustomerOut):
    address: Optional[str] = None
    dob: Optional[str] = None
    accounts: List[AccountOut] = []


class TransactionOut(BaseModel):
    id: str
    txn_id: str
    account_id: str
    account_number_masked: Optional[str] = None
    posted_at: datetime
    direction: str
    amount: float
    currency: str = "INR"
    channel: str
    category: Optional[str] = None
    narration: Optional[str] = None
    counterparty: Optional[str] = None
    counterparty_account_masked: Optional[str] = None
    balance_after: Optional[float] = None
    status: str

    @classmethod
    def from_txn(cls, t: Transaction, acc_number: Optional[str] = None) -> "TransactionOut":
        return cls(
            id=str(t.id),
            txn_id=t.txn_id,
            account_id=str(t.account_id),
            account_number_masked=_mask_account(acc_number) if acc_number else None,
            posted_at=t.posted_at,
            direction=t.direction,
            amount=float(t.amount or 0),
            currency=t.currency,
            channel=t.channel,
            category=t.category,
            narration=t.narration,
            counterparty=t.counterparty,
            counterparty_account_masked=_mask_account(t.counterparty_account) if t.counterparty_account else None,
            balance_after=float(t.balance_after) if t.balance_after is not None else None,
            status=t.status,
        )


class LoanOut(BaseModel):
    id: str
    loan_id: str
    customer_id: str
    customer_name: Optional[str] = None
    product: str
    amount: float
    tenure_months: int
    interest_rate: Optional[float] = None
    emi: Optional[float] = None
    purpose: Optional[str] = None
    status: str
    stage: Optional[str] = None
    branch_code: Optional[str] = None
    created_at: datetime
    decided_at: Optional[datetime] = None
    remarks: Optional[str] = None

    @classmethod
    def from_loan(cls, l: LoanApplication, customer: Optional[Customer] = None) -> "LoanOut":
        return cls(
            id=str(l.id),
            loan_id=l.loan_id,
            customer_id=str(l.customer_id),
            customer_name=customer.name if customer else None,
            product=l.product,
            amount=float(l.amount or 0),
            tenure_months=l.tenure_months,
            interest_rate=float(l.interest_rate) if l.interest_rate is not None else None,
            emi=float(l.emi) if l.emi is not None else None,
            purpose=l.purpose,
            status=l.status,
            stage=l.stage,
            branch_code=l.branch_code,
            created_at=l.created_at,
            decided_at=l.decided_at,
            remarks=l.remarks,
        )


class LoanCreate(BaseModel):
    customer_id: str
    product: str
    amount: float
    tenure_months: int
    purpose: Optional[str] = None


class KycOut(BaseModel):
    id: str
    case_number: str
    customer_id: str
    customer_name: Optional[str] = None
    case_type: str
    status: str
    priority: str
    documents_pending: List[str] = []
    risk_rating: Optional[str] = None
    due_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime

    @classmethod
    def from_case(cls, k: KycCase, customer: Optional[Customer] = None) -> "KycOut":
        return cls(
            id=str(k.id),
            case_number=k.case_number,
            customer_id=str(k.customer_id),
            customer_name=customer.name if customer else None,
            case_type=k.case_type,
            status=k.status,
            priority=k.priority,
            documents_pending=k.documents_pending or [],
            risk_rating=k.risk_rating,
            due_at=k.due_at,
            notes=k.notes,
            created_at=k.created_at,
        )


class KycUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class DocumentOut(BaseModel):
    id: str
    doc_id: str
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    title: str
    doc_type: Optional[str] = None
    file_name: str
    file_size: Optional[int] = None
    mime: Optional[str] = None
    version: int = 1
    status: str
    created_at: datetime

    @classmethod
    def from_doc(cls, d: PortalDocument, customer: Optional[Customer] = None) -> "DocumentOut":
        return cls(
            id=str(d.id),
            doc_id=d.doc_id,
            customer_id=str(d.customer_id) if d.customer_id else None,
            customer_name=customer.name if customer else None,
            title=d.title,
            doc_type=d.doc_type,
            file_name=d.file_name,
            file_size=d.file_size,
            mime=d.mime,
            version=d.version,
            status=d.status,
            created_at=d.created_at,
        )


class DocumentCreate(BaseModel):
    customer_id: Optional[str] = None
    title: str
    doc_type: str = "OTHER"
    file_name: str
    file_size: Optional[int] = None
    mime: Optional[str] = None


class TicketOut(BaseModel):
    id: str
    ticket_number: str
    category: str
    subject: str
    description: Optional[str] = None
    priority: str
    status: str
    assignee_name: Optional[str] = None
    resolution: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_ticket(cls, t: SupportTicket) -> "TicketOut":
        return cls(
            id=str(t.id),
            ticket_number=t.ticket_number,
            category=t.category,
            subject=t.subject,
            description=t.description,
            priority=t.priority,
            status=t.status,
            assignee_name=t.assignee_name,
            resolution=t.resolution,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )


class TicketCreate(BaseModel):
    category: str
    subject: str
    description: Optional[str] = None
    priority: str = "MEDIUM"


class TransferRequest(BaseModel):
    from_account_id: str
    to_account_number: str
    amount: float
    channel: str = "IMPS"
    narration: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v):
        if v <= 0:
            raise ValueError("amount must be positive")
        return round(v, 2)


class TransferResponse(BaseModel):
    txn_id: str
    status: str
    amount: float
    from_account_masked: str
    to_account_masked: str
    balance_after: float
    channel: str
    reference: str
    posted_at: datetime


class PortalNotificationOut(BaseModel):
    id: str
    category: str
    title: str
    body: Optional[str] = None
    link: Optional[str] = None
    read: bool
    created_at: datetime

    @classmethod
    def from_row(cls, n: PortalNotification) -> "PortalNotificationOut":
        return cls(
            id=str(n.id), category=n.category, title=n.title, body=n.body,
            link=n.link, read=n.read, created_at=n.created_at,
        )


class PortalNotificationList(BaseModel):
    items: List[PortalNotificationOut]
    unread: int


class Paged(BaseModel):
    items: list
    page: int
    page_size: int
    total: int
    total_pages: int


# ---------------------------------------------------------------------------
# Profile & branch
# ---------------------------------------------------------------------------

@router.get("/profile", response_model=BankProfileResponse)
def bank_profile(current_user: User = Depends(require_bank_staff)):
    role = sorted(roles_of(current_user) & BANKING_ROLES)
    primary = next((r for r in ["BRANCH_MANAGER", "RELATIONSHIP_MANAGER", "COMPLIANCE_OFFICER",
                                "OPERATIONS_MANAGER", "TELLER"] if r in role), role[0] if role else "TELLER")
    perms = []
    if _has(current_user, TRANSFERS_ALLOWED): perms.append("transfers")
    if _has(current_user, LOANS_ALLOWED): perms.append("loans")
    if _has(current_user, KYC_ALLOWED): perms.append("kyc")
    if _has(current_user, DOCS_ALLOWED): perms.append("documents")
    perms += ["customers", "accounts", "transactions", "statements", "support", "notifications"]
    return BankProfileResponse(
        id=str(current_user.id), name=current_user.name, email=current_user.email,
        role=primary, employee_code=current_user.employee_code, job_title=current_user.job_title,
        department=current_user.department, branch_code=current_user.branch_code,
        branch_name=current_user.branch_name, mfa_enabled=current_user.mfa_enabled,
        last_login=current_user.last_login, permissions=perms,
    )


@router.get("/branches", response_model=List[BranchOut])
def list_branches(current_user: User = Depends(require_bank_staff), db: Session = Depends(get_db)):
    return db.query(Branch).order_by(Branch.name).all()


@router.get("/branches/{code}", response_model=BranchOut)
def get_branch(code: str, current_user: User = Depends(require_bank_staff), db: Session = Depends(get_db)):
    branch = db.query(Branch).filter(Branch.code == code).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    return branch


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

@router.get("/customers")
def search_customers(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    q: Optional[str] = Query(None, description="name / customer id / phone"),
    segment: Optional[str] = None,
    kyc_status: Optional[str] = None,
    current_user: User = Depends(require_bank_staff),
    db: Session = Depends(get_db),
):
    query = db.query(Customer)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            Customer.name.ilike(like),
            Customer.customer_id.ilike(like),
            Customer.phone.ilike(like),
            Customer.email.ilike(like),
        ))
    if segment:
        query = query.filter(Customer.segment == segment)
    if kyc_status:
        query = query.filter(Customer.kyc_status == kyc_status)

    total = query.count()
    rows = (query.order_by(Customer.name)
            .offset((page - 1) * page_size).limit(page_size).all())

    _mirror_telemetry(db, current_user, request, "customer_search",
                      f"search:{q or '*'}", metadata={"results": len(rows)})

    return Paged(
        items=[CustomerOut.from_customer(c).model_dump() for c in rows],
        page=page, page_size=page_size, total=total,
        total_pages=math.ceil(total / page_size) if total else 1,
    )


@router.get("/customers/{customer_id}")
def customer_detail(
    customer_id: str,
    request: Request,
    current_user: User = Depends(require_bank_staff),
    db: Session = Depends(get_db),
):
    c = db.query(Customer).filter(Customer.id == customer_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")

    accounts = db.query(BankAccount).filter(BankAccount.customer_id == c.id).all()
    detail = CustomerDetailOut.from_customer(c)
    detail.address = c.address
    detail.dob = c.dob
    detail.accounts = [AccountOut.from_account(a) for a in accounts]

    _mirror_telemetry(db, current_user, request, "customer_profile_view", f"customer:{c.customer_id}",
                      customer=c)
    return detail.model_dump()


# ---------------------------------------------------------------------------
# Accounts & transactions
# ---------------------------------------------------------------------------

@router.get("/accounts/{account_id}")
def account_detail(
    account_id: str,
    request: Request,
    current_user: User = Depends(require_bank_staff),
    db: Session = Depends(get_db),
):
    a = db.query(BankAccount).filter(BankAccount.id == account_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Account not found")
    c = db.query(Customer).filter(Customer.id == a.customer_id).first()
    out = AccountOut.from_account(a).model_dump()
    out["customer_id"] = str(a.customer_id)
    out["customer_name"] = c.name if c else None
    _mirror_telemetry(db, current_user, request, "account_view", f"account:{a.account_number}",
                      customer=c)
    return out


@router.get("/accounts/{account_id}/transactions")
def account_transactions(
    account_id: str,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=100),
    direction: Optional[str] = Query(None, description="DR|CR"),
    channel: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(require_bank_staff),
    db: Session = Depends(get_db),
):
    a = db.query(BankAccount).filter(BankAccount.id == account_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Account not found")
    query = db.query(Transaction).filter(Transaction.account_id == a.id)
    if direction:
        query = query.filter(Transaction.direction == direction.upper())
    if channel:
        query = query.filter(Transaction.channel == channel.upper())
    if status:
        query = query.filter(Transaction.status == status.upper())
    total = query.count()
    rows = query.order_by(Transaction.posted_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    _mirror_telemetry(db, current_user, request, "transaction_history_view", f"account:{a.account_number}",
                      metadata={"rows": len(rows)}, customer=c)
    return Paged(
        items=[TransactionOut.from_txn(t, a.account_number).model_dump() for t in rows],
        page=page, page_size=page_size, total=total,
        total_pages=math.ceil(total / page_size) if total else 1,
    )


@router.get("/transactions")
def recent_transactions(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: Optional[str] = Query(None, description="txn id / counterparty"),
    channel: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(require_bank_staff),
    db: Session = Depends(get_db),
):
    query = db.query(Transaction).join(BankAccount, BankAccount.id == Transaction.account_id)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            Transaction.txn_id.ilike(like),
            Transaction.counterparty.ilike(like),
            Transaction.narration.ilike(like),
        ))
    if channel:
        query = query.filter(Transaction.channel == channel.upper())
    if status:
        query = query.filter(Transaction.status == status.upper())

    total = query.count()
    rows = query.order_by(Transaction.posted_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    acc_numbers = {a.id: a.account_number for a in db.query(BankAccount).all()}
    _mirror_telemetry(db, current_user, request, "transactions_view", f"transactions:{q or '*'}")
    return Paged(
        items=[TransactionOut.from_txn(t, acc_numbers.get(t.account_id)).model_dump() for t in rows],
        page=page, page_size=page_size, total=total,
        total_pages=math.ceil(total / page_size) if total else 1,
    )


# ---------------------------------------------------------------------------
# Fund transfer
# ---------------------------------------------------------------------------

@router.post("/transfers", response_model=TransferResponse, status_code=201)
def create_transfer(
    payload: TransferRequest,
    request: Request,
    current_user: User = Depends(require_bank_staff),
    db: Session = Depends(get_db),
):
    if not _has(current_user, TRANSFERS_ALLOWED):
        raise HTTPException(status_code=403, detail="Not permitted to create transfers")
    if payload.amount > 10_000_00:
        raise HTTPException(status_code=422, detail="Amount exceeds portal limit (₹10,00,000). Visit the branch counter.")

    src = db.query(BankAccount).filter(BankAccount.id == payload.from_account_id).first()
    if not src:
        raise HTTPException(status_code=404, detail="Source account not found")
    if src.status != "ACTIVE":
        raise HTTPException(status_code=422, detail=f"Source account is {src.status}")
    if float(src.balance or 0) < payload.amount:
        raise HTTPException(status_code=422, detail="Insufficient balance")

    dst = db.query(BankAccount).filter(BankAccount.account_number == payload.to_account_number).first()
    if not dst:
        raise HTTPException(status_code=404, detail="Destination account not found")
    if dst.id == src.id:
        raise HTTPException(status_code=422, detail="Source and destination cannot be the same")

    now = datetime.now(timezone.utc)
    amount = Decimal(str(payload.amount))
    src.balance = (src.balance or Decimal(0)) - amount
    dst.balance = (dst.balance or Decimal(0)) + amount
    src.last_txn_at = now
    dst.last_txn_at = now

    ref = secrets.token_hex(6).upper()
    out_txn = Transaction(
        txn_id=_gen_txn_id(), account_id=src.id, posted_at=now, direction="DR",
        amount=amount, currency=src.currency, channel=payload.channel.upper(),
        category="TRANSFER", narration=payload.narration or "Portal transfer",
        counterparty=None, counterparty_account=dst.account_number,
        balance_after=src.balance, status="SUCCESS", reference=ref,
    )
    in_txn = Transaction(
        txn_id=_gen_txn_id(), account_id=dst.id, posted_at=now, direction="CR",
        amount=amount, currency=dst.currency, channel=payload.channel.upper(),
        category="TRANSFER", narration=payload.narration or "Portal credit",
        counterparty=None, counterparty_account=src.account_number,
        balance_after=dst.balance, status="SUCCESS", reference=ref,
    )
    db.add_all([out_txn, in_txn])
    db.flush()

    resp = TransferResponse(
        txn_id=out_txn.txn_id, status="SUCCESS", amount=payload.amount,
        from_account_masked=_mask_account(src.account_number),
        to_account_masked=_mask_account(dst.account_number),
        balance_after=float(src.balance), channel=payload.channel.upper(),
        reference=ref, posted_at=now,
    )

    # Alert both the operator and (conceptually) the branch — portal notification
    _notify(db, current_user.id, "TRANSFERS",
            f"Transfer {resp.txn_id} successful",
            f"₹{payload.amount:,.2f} from a/c {resp.from_account_masked} to {resp.to_account_masked} via {resp.channel}. Ref {ref}.")

    _mirror_telemetry(db, current_user, request, "fund_transfer", f"transfer:{resp.txn_id}",
                      event_type="DATA_ACCESS",
                      metadata={"amount": payload.amount, "channel": resp.channel,
                                "to": resp.to_account_masked, "from": resp.from_account_masked})
    db.commit()
    return resp


# ---------------------------------------------------------------------------
# Loans
# ---------------------------------------------------------------------------

@router.get("/loans")
def list_loans(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[str] = None,
    q: Optional[str] = None,
    current_user: User = Depends(require_bank_staff),
    db: Session = Depends(get_db),
):
    query = db.query(LoanApplication)
    if status:
        query = query.filter(LoanApplication.status == status.upper())
    if q:
        like = f"%{q}%"
        query = query.join(Customer).filter(or_(LoanApplication.loan_id.ilike(like), Customer.name.ilike(like)))
    total = query.count()
    rows = query.order_by(LoanApplication.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    cust_ids = {r.customer_id for r in rows}
    custs = {c.id: c for c in db.query(Customer).filter(Customer.id.in_(cust_ids))} if cust_ids else {}
    _mirror_telemetry(db, current_user, request, "loans_view", "loans")
    return Paged(
        items=[LoanOut.from_loan(l, custs.get(l.customer_id)).model_dump() for l in rows],
        page=page, page_size=page_size, total=total,
        total_pages=math.ceil(total / page_size) if total else 1,
    )


@router.post("/loans", status_code=201)
def create_loan(
    payload: LoanCreate,
    request: Request,
    current_user: User = Depends(require_bank_staff),
    db: Session = Depends(get_db),
):
    if not _has(current_user, LOANS_ALLOWED):
        raise HTTPException(status_code=403, detail="Not permitted to create loan applications")
    c = db.query(Customer).filter(Customer.id == payload.customer_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")

    rates = {"HOME": 8.60, "AUTO": 9.20, "PERSONAL": 11.40, "GOLD": 9.80, "EDUCATION": 8.10}
    rate = rates.get(payload.product.upper(), 10.5)
    r = rate / 12 / 100
    n = payload.tenure_months
    emi = round(payload.amount * r * (1 + r) ** n / ((1 + r) ** n - 1), 2) if r else round(payload.amount / n, 2)

    year = datetime.now().year
    seq = db.query(func.count(LoanApplication.id)).scalar() or 0
    loan = LoanApplication(
        loan_id=f"LN-{year}-{(seq + 101):04d}", customer_id=c.id,
        product=payload.product.upper(), amount=payload.amount,
        tenure_months=payload.tenure_months, interest_rate=rate, emi=emi,
        purpose=payload.purpose, status="SUBMITTED", stage="DOC_COLLECTION",
        branch_code=current_user.branch_code, created_by=current_user.id,
    )
    db.add(loan)
    db.flush()
    _notify(db, current_user.id, "LOANS", f"Loan {loan.loan_id} submitted",
            f"{payload.product.title()} loan for {c.name} — ₹{payload.amount:,.2f} for {payload.tenure_months} months.")
    _mirror_telemetry(db, current_user, request, "loan_application_created",
                      f"loan:{loan.loan_id}", metadata={"customer": c.customer_id, "amount": payload.amount})
    db.commit()
    return LoanOut.from_loan(loan, c).model_dump()


@router.patch("/loans/{loan_id}", status_code=200)
def update_loan(
    loan_id: str,
    payload: dict,
    request: Request,
    current_user: User = Depends(require_bank_staff),
    db: Session = Depends(get_db),
):
    if not _has(current_user, LOANS_ALLOWED):
        raise HTTPException(status_code=403, detail="Not permitted to update loans")
    loan = db.query(LoanApplication).filter(LoanApplication.loan_id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    new_status = payload.get("status")
    allowed = {"SUBMITTED", "UNDER_REVIEW", "APPROVED", "REJECTED", "DISBURSED"}
    if new_status:
        if new_status not in allowed:
            raise HTTPException(status_code=422, detail=f"status must be one of {sorted(allowed)}")
        loan.status = new_status
        loan.decided_at = datetime.now(timezone.utc) if new_status in {"APPROVED", "REJECTED", "DISBURSED"} else None
        if new_status == "APPROVED" and not loan.stage:
            loan.stage = "DISBURSEMENT_PENDING"
    if payload.get("stage"):
        loan.stage = payload["stage"]
    if payload.get("remarks") is not None:
        loan.remarks = payload["remarks"]

    _notify(db, current_user.id, "LOANS", f"Loan {loan.loan_id} → {loan.status}",
            payload.get("remarks") or None)
    _mirror_telemetry(db, current_user, request, "loan_status_changed",
                      f"loan:{loan.loan_id}", metadata={"status": loan.status})
    db.commit()
    c = db.query(Customer).filter(Customer.id == loan.customer_id).first()
    return LoanOut.from_loan(loan, c).model_dump()


# ---------------------------------------------------------------------------
# KYC
# ---------------------------------------------------------------------------

@router.get("/kyc")
def list_kyc(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[str] = None,
    priority: Optional[str] = None,
    current_user: User = Depends(require_bank_staff),
    db: Session = Depends(get_db),
):
    query = db.query(KycCase)
    if status:
        query = query.filter(KycCase.status == status.upper())
    if priority:
        query = query.filter(KycCase.priority == priority.upper())
    total = query.count()
    rows = query.order_by(KycCase.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    cust_ids = {r.customer_id for r in rows}
    custs = {c.id: c for c in db.query(Customer).filter(Customer.id.in_(cust_ids))} if cust_ids else {}
    _mirror_telemetry(db, current_user, request, "kyc_view", "kyc")
    return Paged(
        items=[KycOut.from_case(k, custs.get(k.customer_id)).model_dump() for k in rows],
        page=page, page_size=page_size, total=total,
        total_pages=math.ceil(total / page_size) if total else 1,
    )


@router.patch("/kyc/{case_number}")
def update_kyc(
    case_number: str,
    payload: KycUpdate,
    request: Request,
    current_user: User = Depends(require_bank_staff),
    db: Session = Depends(get_db),
):
    if not _has(current_user, KYC_ALLOWED):
        raise HTTPException(status_code=403, detail="Not permitted to update KYC cases")
    k = db.query(KycCase).filter(KycCase.case_number == case_number).first()
    if not k:
        raise HTTPException(status_code=404, detail="KYC case not found")
    allowed = {"PENDING", "IN_REVIEW", "VERIFIED", "REJECTED"}
    if payload.status:
        if payload.status not in allowed:
            raise HTTPException(status_code=422, detail=f"status must be one of {sorted(allowed)}")
        k.status = payload.status
        if payload.status == "VERIFIED":
            c = db.query(Customer).filter(Customer.id == k.customer_id).first()
            if c:
                c.kyc_status = "VERIFIED"
                c.kyc_expiry = datetime.now(timezone.utc) + timedelta(days=365 * 5)
    if payload.notes is not None:
        k.notes = payload.notes

    _notify(db, current_user.id, "KYC", f"KYC {k.case_number} → {k.status}")
    _mirror_telemetry(db, current_user, request, "kyc_status_changed",
                      f"kyc:{k.case_number}", metadata={"status": k.status})
    db.commit()
    c = db.query(Customer).filter(Customer.id == k.customer_id).first()
    return KycOut.from_case(k, c).model_dump()


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------

@router.get("/accounts/{account_id}/statement")
def account_statement(
    account_id: str,
    request: Request,
    months: int = Query(6, ge=1, le=36),
    current_user: User = Depends(require_bank_staff),
    db: Session = Depends(get_db),
):
    a = db.query(BankAccount).filter(BankAccount.id == account_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Account not found")
    c = db.query(Customer).filter(Customer.id == a.customer_id).first()
    since = datetime.now(timezone.utc) - timedelta(days=months * 30)
    txns = (db.query(Transaction)
            .filter(Transaction.account_id == a.id, Transaction.posted_at >= since)
            .order_by(Transaction.posted_at.desc()).limit(200).all())

    _mirror_telemetry(db, current_user, request, "statement_download",
                      f"statement:{a.account_number}", event_type="FILE_UPLOAD",
                      metadata={"months": months, "rows": len(txns)})

    total_dr = sum(float(t.amount) for t in txns if t.direction == "DR")
    total_cr = sum(float(t.amount) for t in txns if t.direction == "CR")
    return {
        "account": AccountOut.from_account(a).model_dump(),
        "customer_name": c.name if c else None,
        "period_months": months,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {"total_debits": round(total_dr, 2), "total_credits": round(total_cr, 2),
                    "txn_count": len(txns)},
        "transactions": [TransactionOut.from_txn(t, a.account_number).model_dump() for t in txns],
    }


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

@router.get("/documents")
def list_documents(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    q: Optional[str] = None,
    doc_type: Optional[str] = None,
    customer_id: Optional[str] = None,
    current_user: User = Depends(require_bank_staff),
    db: Session = Depends(get_db),
):
    query = db.query(PortalDocument)
    if doc_type:
        query = query.filter(PortalDocument.doc_type == doc_type.upper())
    if customer_id:
        query = query.filter(PortalDocument.customer_id == customer_id)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(PortalDocument.title.ilike(like), PortalDocument.file_name.ilike(like)))
    total = query.count()
    rows = query.order_by(PortalDocument.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    cust_ids = {r.customer_id for r in rows if r.customer_id}
    custs = {c.id: c for c in db.query(Customer).filter(Customer.id.in_(cust_ids))} if cust_ids else {}
    _mirror_telemetry(db, current_user, request, "documents_view", "documents")
    return Paged(
        items=[DocumentOut.from_doc(d, custs.get(d.customer_id)).model_dump() for d in rows],
        page=page, page_size=page_size, total=total,
        total_pages=math.ceil(total / page_size) if total else 1,
    )


@router.post("/documents", status_code=201)
def create_document(
    payload: DocumentCreate,
    request: Request,
    current_user: User = Depends(require_bank_staff),
    db: Session = Depends(get_db),
):
    if not _has(current_user, DOCS_ALLOWED):
        raise HTTPException(status_code=403, detail="Not permitted to upload documents")
    seq = db.query(func.count(PortalDocument.id)).scalar() or 0
    doc = PortalDocument(
        doc_id=f"DOC-{(seq + 3001):04d}", customer_id=payload.customer_id,
        uploaded_by=current_user.id, title=payload.title,
        doc_type=payload.doc_type.upper(), file_name=payload.file_name,
        file_size=payload.file_size, mime=payload.mime,
        branch_code=current_user.branch_code,
    )
    db.add(doc)
    db.flush()
    _mirror_telemetry(db, current_user, request, "document_uploaded",
                      f"document:{doc.doc_id}", event_type="FILE_UPLOAD",
                      metadata={"file": payload.file_name, "size": payload.file_size})
    db.commit()
    c = db.query(Customer).filter(Customer.id == doc.customer_id).first() if doc.customer_id else None
    return DocumentOut.from_doc(doc, c).model_dump()


# ---------------------------------------------------------------------------
# Notifications (portal)
# ---------------------------------------------------------------------------

@router.get("/notifications", response_model=PortalNotificationList)
def portal_notifications(
    current_user: User = Depends(require_bank_staff),
    db: Session = Depends(get_db),
):
    rows = (db.query(PortalNotification)
            .filter(PortalNotification.user_id == current_user.id)
            .order_by(PortalNotification.created_at.desc())
            .limit(50).all())
    unread = (db.query(func.count(PortalNotification.id))
              .filter(PortalNotification.user_id == current_user.id, PortalNotification.read == False)
              .scalar()) or 0
    return PortalNotificationList(items=[PortalNotificationOut.from_row(n) for n in rows], unread=unread)


@router.patch("/notifications/{notification_id}/read")
def mark_portal_notification_read(
    notification_id: str,
    current_user: User = Depends(require_bank_staff),
    db: Session = Depends(get_db),
):
    n = db.query(PortalNotification).filter(
        PortalNotification.id == notification_id,
        PortalNotification.user_id == current_user.id,
    ).first()
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.read = True
    db.commit()
    return {"ok": True}


@router.patch("/notifications/read-all")
def mark_all_portal_notifications_read(
    current_user: User = Depends(require_bank_staff),
    db: Session = Depends(get_db),
):
    db.query(PortalNotification).filter(
        PortalNotification.user_id == current_user.id,
        PortalNotification.read == False,
    ).update({"read": True})
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Support tickets
# ---------------------------------------------------------------------------

@router.get("/support/tickets")
def list_tickets(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[str] = None,
    current_user: User = Depends(require_bank_staff),
    db: Session = Depends(get_db),
):
    query = db.query(SupportTicket).filter(SupportTicket.raised_by == current_user.id)
    if status:
        query = query.filter(SupportTicket.status == status.upper())
    total = query.count()
    rows = query.order_by(SupportTicket.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return Paged(
        items=[TicketOut.from_ticket(t).model_dump() for t in rows],
        page=page, page_size=page_size, total=total,
        total_pages=math.ceil(total / page_size) if total else 1,
    )


@router.post("/support/tickets", status_code=201)
def create_ticket(
    payload: TicketCreate,
    request: Request,
    current_user: User = Depends(require_bank_staff),
    db: Session = Depends(get_db),
):
    seq = db.query(func.count(SupportTicket.id)).scalar() or 0
    t = SupportTicket(
        ticket_number=f"TCK-{(seq + 2001):04d}", raised_by=current_user.id,
        category=payload.category.upper(), subject=payload.subject,
        description=payload.description, priority=payload.priority.upper(),
    )
    db.add(t)
    db.flush()
    _mirror_telemetry(db, current_user, request, "support_ticket_created",
                      f"ticket:{t.ticket_number}", metadata={"category": t.category})
    db.commit()
    return TicketOut.from_ticket(t).model_dump()
