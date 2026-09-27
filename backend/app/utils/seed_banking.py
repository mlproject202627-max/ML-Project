"""Rich, realistic seed data for the banking employee portal.

Idempotent: skips entirely when bank customers already exist (except that it
always makes sure demo employee accounts exist). Safe to run on every boot.

    cd backend && venv/bin/python -m app.utils.seed_banking
"""
import random
import secrets
from datetime import datetime, timedelta, timezone

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User, Role, user_roles
from app.models.banking import (
    Branch, Customer, BankAccount, Transaction,
    LoanApplication, KycCase, PortalDocument, SupportTicket, PortalNotification,
)

rng = random.Random(42)

FIRST = ["Aarav", "Vivaan", "Aditya", "Ishaan", "Kabir", "Rohan", "Arjun", "Rahul",
         "Priya", "Ananya", "Diya", "Meera", "Kavya", "Sneha", "Riya", "Nisha",
         "Vikram", "Sanjay", "Deepak", "Pooja", "Neha", "Aisha", "Farhan", "Sameer",
         "Lakshmi", "Srinivas", "Ramesh", "Harini", "Divya", "Karthik"]
LAST = ["Sharma", "Verma", "Reddy", "Iyer", "Nair", "Patel", "Gupta", "Rao",
        "Menon", "Joshi", "Desai", "Kulkarni", "Chowdary", "Bhat", "Shetty",
        "Pillai", "Mohan", "Das", "Kapoor", "Sinha"]
CITIES = [("Vijayawada", "Andhra Pradesh"), ("Hyderabad", "Telangana"), ("Visakhapatnam", "Andhra Pradesh"),
          ("Guntur", "Andhra Pradesh"), ("Warangal", "Telangana")]
SEGMENTS = ["RETAIL", "RETAIL", "RETAIL", "PREMIUM", "PREMIUM", "BUSINESS", "STAFF"]
CHANNELS = ["UPI", "UPI", "UPI", "NEFT", "IMPS", "ATM", "POS", "BRANCH", "ACH"]
CATEGORIES = ["SALARY", "RENT", "GROCERY", "UTILITIES", "SHOPPING", "DINING", "TRAVEL",
              "MEDICAL", "EDUCATION", "TRANSFER", "EMI"]
MERCHANTS = ["BigBasket", "Reliance Fresh", "Indian Oil", "Swiggy", "IRCTC", "Apollo Pharmacy",
             "Amazon", "Flipkart", "Zomato", "Airtel Postpaid", "Paytm Recharge", "Spencers"]
LOAN_PRODUCTS = ["HOME", "AUTO", "PERSONAL", "GOLD", "EDUCATION"]
LOAN_STATUS = ["SUBMITTED", "UNDER_REVIEW", "APPROVED", "REJECTED", "DISBURSED"]
DOC_TYPES = ["ID_PROOF", "ADDRESS_PROOF", "INCOME_PROOF", "FORM_16", "STATEMENT", "OTHER"]

BRANCHES = [
    ("VJA-CENTRAL", "Vijayawada Central", "SBIN0VJA01", "23-4-12 MG Road, Beside SVM Cinema", "Vijayawada", "Andhra Pradesh", "+91 866 257 1100", "Rajesh Kumar"),
    ("HYD-BANJARA", "Hyderabad Banjara Hills", "SBIN0HYDBJ", "Plot 44, Road No 12, Banjara Hills", "Hyderabad", "Telangana", "+91 40 2354 8800", "Sunita Rao"),
    ("VIZAG-NAV", "Visakhapatnam Naval", "SBIN0VZGNV", "1-22 Beach Road, Near Naval Base", "Visakhapatnam", "Andhra Pradesh", "+91 891 278 4400", "Anand Varma"),
]


def pick_name(used):
    while True:
        n = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        if n not in used:
            used.add(n)
            return n


def _phone():
    return f"+91 {rng.randint(70, 99)}{rng.randint(10000000, 99999999)}"


def _account_number():
    return f"{rng.randint(10000000000, 99999999999)}" + str(rng.randint(0, 9))


def _setup_demo_employees(db) -> list[User]:
    """Ensure one ACTIVE demo login per banking role (password ChangeMe#123)."""
    demo = [
        ("Meera Krishnan", "meera.krishnan@sentinel.in", "TELLER", "VJA-CENTRAL", "Vijayawada Central", "Senior Teller", "Branch Ops"),
        ("Arjun Nair", "arjun.nair@sentinel.in", "RELATIONSHIP_MANAGER", "VJA-CENTRAL", "Vijayawada Central", "Relationship Manager", "Retail Banking"),
        ("Sunita Rao", "sunita.rao@sentinel.in", "BRANCH_MANAGER", "HYD-BANJARA", "Hyderabad Banjara Hills", "Branch Manager", "Branch Ops"),
        ("Farhan Ali", "farhan.ali@sentinel.in", "COMPLIANCE_OFFICER", "VJA-CENTRAL", "Vijayawada Central", "Compliance Officer", "Compliance"),
        ("Deepak Menon", "deepak.menon@sentinel.in", "OPERATIONS_MANAGER", "VIZAG-NAV", "Visakhapatnam Naval", "Operations Manager", "Operations"),
    ]
    users = []
    for name, email, role_name, bcode, bname, title, dept in demo:
        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            continue
        u = db.query(User).filter(User.email == email).first()
        if not u:
            u = User(
                name=name, email=email, password_hash=hash_password("ChangeMe#123"),
                department=dept, job_title=title, status="ACTIVE",
                employee_code=f"EMP-{rng.randint(10000, 99999)}",
                branch_code=bcode, branch_name=bname, mfa_enabled=True,
            )
            db.add(u)
            db.flush()
            db.execute(user_roles.insert().values(user_id=u.id, role_id=role.id))
            db.flush()
            db.add(PortalNotification(
                user_id=u.id, category="GENERAL",
                title=f"Welcome to Apna Bank Portal, {name.split()[0]}!",
                body="Your staff account is ready. Reach out to IT support for any access issues.",
            ))
        users.append(u)
    return users


def seed():
    db = SessionLocal()
    try:
        employees = _setup_demo_employees(db)
        db.commit()

        if db.query(Customer).count() > 0:
            print("Banking data already present — skipping customer seed.")
            return

        branches = {}
        for code, name, ifsc, addr, city, state, phone, mgr in BRANCHES:
            b = db.query(Branch).filter(Branch.code == code).first()
            if not b:
                b = Branch(code=code, name=name, ifsc=ifsc, address=addr, city=city,
                           state=state, phone=phone, manager_name=mgr)
                db.add(b)
                db.flush()
            branches[code] = b

        now = datetime.now(timezone.utc)
        used_names, used_cust, used_acc, used_txn = set(), set(), set(), set()

        customers = []
        for i in range(48):
            while True:
                cid = f"CUST-{rng.randint(10000, 99999)}"
                if cid not in used_cust:
                    used_cust.add(cid)
                    break
            name = pick_name(used_names)
            city, state = rng.choice(CITIES)
            kyc = rng.choices(["VERIFIED", "PENDING", "EXPIRED", "REJECTED"], weights=[70, 18, 7, 5])[0]
            branch_code = rng.choice(list(branches))
            c = Customer(
                customer_id=cid, name=name,
                email=f"{name.lower().replace(' ', '.')}@gmail.com",
                phone=_phone(),
                pan=f"{rng.choice('ABCDEGHJKLMNPQRSTUVWXY')}{rng.choice('ABCDE')}{rng.choice('FPA')}"
                    f"{rng.randint(1000, 9999)}{rng.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}",
                aadhaar_masked=f"XXXXXXXX{rng.randint(1000, 9999)}",
                dob=f"{rng.randint(1965, 2003)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
                address=f"{rng.randint(1, 99)}-{'AB' if rng.random() < 0.5 else 'CD'}-{rng.randint(1, 99)}, "
                        f"{rng.choice(['Gandhi Nagar', 'Rose Villa', 'Lake View', 'Palm Springs', 'Sector 7'])}",
                city=city, state=state,
                segment=rng.choice(SEGMENTS),
                risk_rating=rng.choices(["LOW", "MEDIUM", "HIGH"], weights=[75, 20, 5])[0],
                kyc_status=kyc,
                kyc_expiry=now + timedelta(days=rng.randint(-60, 1800)) if kyc == "VERIFIED" else None,
                relationship_manager=rng.choice([u.name for u in employees]),
                home_branch_code=branch_code,
                created_at=now - timedelta(days=rng.randint(200, 3500)),
            )
            db.add(c)
            customers.append(c)
        db.flush()

        accounts, acc_counter = [], 0
        for c in customers:
            for _ in range(rng.choices([1, 2, 3], weights=[55, 33, 12])[0]):
                acc_counter += 1
                while True:
                    acc_no = _account_number()
                    if acc_no not in used_acc:
                        used_acc.add(acc_no)
                        break
                opened = now - timedelta(days=rng.randint(90, 3000))
                balance = round(rng.uniform(1_500, 1_900_000), 2)
                a = BankAccount(
                    account_number=acc_no, customer_id=c.id,
                    account_type=rng.choices(["SAVINGS", "CURRENT", "SALARY", "FD"],
                                             weights=[52, 20, 20, 8])[0],
                    scheme=rng.choice(["Apna Savings Max", "Apna Business Pro", "Salary Advantage",
                                       "Fixed Deposit 2Y", "Apna Basic Savings"]),
                    balance=balance, currency="INR", status="ACTIVE",
                    opened_at=opened, last_txn_at=now - timedelta(days=rng.randint(0, 12)),
                )
                db.add(a)
                accounts.append(a)
        db.flush()

        txn_counter = 0
        for a in accounts:
            bal = float(a.balance)
            for _ in range(rng.randint(12, 26)):
                txn_counter += 1
                while True:
                    tid = f"TXN-{rng.randint(10000000, 99999999)}"
                    if tid not in used_txn:
                        used_txn.add(tid)
                        break
                dr = rng.random() < 0.55
                amt = round(rng.choices([rng.uniform(80, 4000), rng.uniform(4000, 60000),
                                         rng.uniform(60000, 250000)],
                                        weights=[62, 30, 8])[0], 2)
                posted = now - timedelta(days=rng.randint(0, 120), hours=rng.randint(0, 23),
                                         minutes=rng.randint(0, 59))
                if dr:
                    bal = max(500.0, bal + amt)  # historical reconstruction
                    bal_after = bal - amt
                else:
                    bal_after = bal + amt
                    bal = bal_after
                category = rng.choice(CATEGORIES)
                if category == "SALARY":
                    cp, cp_acc = f"{rng.choice(TECH_COMPANIES)} Payroll", None
                    amt = round(rng.uniform(45000, 210000), 2)
                elif category in ("GROCERY", "SHOPPING", "DINING"):
                    cp, cp_acc = rng.choice(MERCHANTS), None
                elif category == "EMI":
                    cp, cp_acc = "Apna Housing Finance EMI", None
                else:
                    cp, cp_acc = rng.choice(FIRST) + " " + rng.choice(LAST), _account_number()
                db.add(Transaction(
                    txn_id=tid, account_id=a.id, posted_at=posted,
                    direction="DR" if dr else "CR", amount=amt, currency="INR",
                    channel=rng.choice(CHANNELS), category=category,
                    narration=f"{category.title()} {rng.choice(['payment to', 'from', '—'])} {cp}",
                    counterparty=cp, counterparty_account=cp_acc,
                    balance_after=round(bal_after, 2),
                    status=rng.choices(["SUCCESS", "PENDING", "FAILED"], weights=[92, 4, 4])[0],
                    reference=secrets.token_hex(5).upper(),
                ))
        db.flush()

        # Loans
        for i in range(14):
            c = rng.choice(customers)
            product = rng.choice(LOAN_PRODUCTS)
            amount = round(rng.uniform(80_000, 5_500_000), 2)
            tenure = rng.choice([12, 24, 36, 60, 84, 120, 240])
            status = rng.choice(LOAN_STATUS)
            db.add(LoanApplication(
                loan_id=f"LN-2026-{(i + 101):04d}", customer_id=c.id, product=product,
                amount=amount, tenure_months=tenure,
                interest_rate={"HOME": 8.60, "AUTO": 9.20, "PERSONAL": 11.40,
                               "GOLD": 9.80, "EDUCATION": 8.10}[product],
                emi=round(amount / tenure * 1.18, 2),
                purpose=rng.choice(["Home renovation", "New car purchase", "Wedding expenses",
                                    "Medical emergency", "Business expansion", "Higher education"]),
                status=status, stage=rng.choice(["DOC_COLLECTION", "CREDIT_CHECK", "DISBURSEMENT_PENDING"]),
                branch_code=c.home_branch_code, created_by=rng.choice(employees).id,
                created_at=now - timedelta(days=rng.randint(1, 90)),
                remarks="Seeded application",
            ))

        # KYC cases
        for i, c in enumerate(rng.sample(customers, 12)):
            db.add(KycCase(
                case_number=f"KYC-{4500 + i}", customer_id=c.id,
                case_type=rng.choice(["NEW", "PERIODIC", "UPDATE"]),
                status=c.kyc_status if c.kyc_status != "VERIFIED" else rng.choice(["PENDING", "IN_REVIEW"]),
                priority=rng.choices(["HIGH", "MEDIUM", "LOW"], weights=[25, 50, 25])[0],
                documents_pending=rng.sample(["PAN", "AADHAAR", "PHOTO", "INCOME_PROOF", "SIGNATURE"],
                                             rng.randint(0, 3)),
                risk_rating=c.risk_rating,
                due_at=now + timedelta(days=rng.randint(-10, 30)),
                assigned_to=rng.choice(employees).id,
                created_at=now - timedelta(days=rng.randint(1, 45)),
            ))

        # Documents
        for i in range(18):
            c = rng.choice(customers)
            dt = rng.choice(DOC_TYPES)
            size = rng.randint(80_000, 4_500_000)
            db.add(PortalDocument(
                doc_id=f"DOC-{3001 + i}", customer_id=c.id,
                uploaded_by=rng.choice(employees).id,
                title=f"{dt.replace('_', ' ').title()} — {c.name}",
                doc_type=dt, file_name=f"{c.customer_id}_{dt.lower()}.pdf",
                file_size=size, mime="application/pdf",
                status=rng.choices(["UPLOADED", "VERIFIED", "ARCHIVED"], weights=[40, 50, 10])[0],
                branch_code=c.home_branch_code,
                created_at=now - timedelta(days=rng.randint(0, 200)),
            ))

        # Tickets
        tickets = [
            ("IT", "Printer at counter 2 not connecting", "OPEN", "HIGH"),
            ("IT", "Password reset for portal", "RESOLVED", "MEDIUM"),
            ("OPERATIONS", "Cash replenishment delayed", "IN_PROGRESS", "HIGH"),
            ("COMPLIANCE", "Clarification on freeze order", "OPEN", "MEDIUM"),
            ("HR", "Leave balance mismatch", "CLOSED", "LOW"),
        ]
        for i, (cat, subj, st, pri) in enumerate(tickets):
            emp = rng.choice(employees)
            db.add(SupportTicket(
                ticket_number=f"TCK-{2001 + i}", raised_by=emp.id, category=cat,
                subject=subj, description="Auto-seeded ticket", priority=pri, status=st,
                assignee_name=rng.choice(["IT Helpdesk", "Facilities", "Risk Team", "HRMS Bot"]),
                created_at=now - timedelta(days=rng.randint(1, 30)),
            ))

        # A couple of notifications per employee
        for u in employees:
            db.add_all([
                PortalNotification(user_id=u.id, category="LOANS",
                                   title="3 loan applications awaiting your review",
                                   body="Applications LN-2026-0104, LN-2026-0108 and LN-2026-0111.", link="/loans"),
                PortalNotification(user_id=u.id, category="KYC",
                                   title="KYC re-verification due this month",
                                   body="Customers with KYC expiring in the next 30 days need attention.", link="/kyc"),
            ])

        db.commit()
        print(f"Seeded {len(BRANCHES)} branches, {len(customers)} customers, "
              f"{len(accounts)} accounts, {txn_counter} transactions, "
              f"loans/kyc/docs/tickets. Demo employees: {[u.email for u in employees]}")
    finally:
        db.close()


TECH_COMPANIES = ["Infosys", "TCS", "Wipro", "Accenture", "Capgemini", "Deloitte"]


if __name__ == "__main__":
    seed()
