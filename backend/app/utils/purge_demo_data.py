"""Remove ALL demo users, roles' demo accounts, and synthetic data.

Run once:  cd backend && venv/bin/python -m app.utils.purge_demo_data
"""
import sys

from app.core.database import SessionLocal, engine, Base
from app.models import (
    User, Role, Activity, Anomaly, RiskEvent, Investigation, InvestigationEvent,
    DetectionPolicy, Notification, TelemetryEvent, UserSession, AgentKey,
)
from app.models.user import user_roles


def purge() -> None:
    print("Purging demo data...")
    db = SessionLocal()
    try:
        # Ensure new tables exist before we start deleting
        Base.metadata.create_all(bind=engine)

        # Wipe users + all synthetic data. Roles are kept so the first
        # bootstrap-admin can be assigned ADMIN immediately.
        for table in (
            RiskEvent, InvestigationEvent, Investigation, Notification,
            TelemetryEvent, UserSession, AgentKey, Activity, Anomaly,
            DetectionPolicy, user_roles, User,
        ):
            name = getattr(table, "__tablename__", getattr(table, "name", str(table)))
            n = db.query(table).delete(synchronize_session=False)
            print(f"  deleted {n:>5} rows from {name}")
        db.commit()
        print("Done. The instance is now userless; the UI will offer one-time admin bootstrap.")
    finally:
        db.close()


if __name__ == "__main__":
    purge()
