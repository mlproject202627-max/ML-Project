"""
Sentinel UEBA - Database Seed Script

Creates demo users, roles, activities, anomalies, investigations, and detection policies.
All data is SYNTHETIC / DEVELOPMENT DATA — never use in production.

Usage:
    cd backend
    source venv/bin/activate
    python scripts/seed_data.py
"""

import sys
import os
import uuid
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure we can import from the backend package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine, SessionLocal, Base
from app.core.security import hash_password
from app.models.user import User, Role, user_roles
from app.models.activity import Activity
from app.models.anomaly import Anomaly
from app.models.risk_event import RiskEvent
from app.models.investigation import Investigation, InvestigationEvent
from app.models.detection_policy import DetectionPolicy
from app.models.notification import Notification


# ── Demo Credentials ────────────────────────────────────────────────────────
# All passwords are for DEVELOPMENT ONLY
DEMO_PASSWORD = "Admin123!"

USERS_DATA = [
    {
        "email": "admin@sentinel.demo",
        "name": "System Admin",
        "department": "IT Ops",
        "job_title": "Platform Administrator",
        "roles": ["ADMIN"],
        "password": "Admin123!",
    },
    {
        "email": "sarah.chen@sentinel.demo",
        "name": "Sarah Chen",
        "department": "IT Ops",
        "job_title": "Senior Security Analyst",
        "roles": ["SECURITY_ANALYST"],
        "password": "Analyst123!",
    },
    {
        "email": "viewer@sentinel.demo",
        "name": "Alex Morgan",
        "department": "Engineering",
        "job_title": "Software Engineer",
        "roles": ["VIEWER"],
        "password": "Viewer123!",
    },
    {
        "email": "manager@sentinel.demo",
        "name": "Jordan Rivera",
        "department": "IT Ops",
        "job_title": "Security Manager",
        "roles": ["SECURITY_MANAGER"],
        "password": "Manager123!",
    },
    # Additional monitored employees
    {
        "email": "omar.haddad@company.demo",
        "name": "Omar Haddad",
        "department": "IT Ops",
        "job_title": "Systems Administrator",
        "roles": ["VIEWER"],
        "password": "User123!",
    },
    {
        "email": "derek.hollis@company.demo",
        "name": "Derek Hollis",
        "department": "Finance",
        "job_title": "Contract Data Analyst",
        "roles": ["VIEWER"],
        "password": "User123!",
    },
    {
        "email": "elena.petrova@company.demo",
        "name": "Elena Petrova",
        "department": "Sales",
        "job_title": "Account Executive",
        "roles": ["VIEWER"],
        "password": "User123!",
    },
    {
        "email": "priya.raghavan@company.demo",
        "name": "Priya Raghavan",
        "department": "Finance",
        "job_title": "Senior Financial Analyst",
        "roles": ["VIEWER"],
        "password": "User123!",
    },
    {
        "email": "rajesh.kumar@company.demo",
        "name": "Rajesh Kumar",
        "department": "IT Ops",
        "job_title": "DevOps Engineer",
        "roles": ["VIEWER"],
        "password": "User123!",
    },
]

ROLE_DEFINITIONS = [
    ("ADMIN", "Full system access"),
    ("SECURITY_MANAGER", "Security management, investigations, policies"),
    ("SECURITY_ANALYST", "Detection, investigations, analysis"),
    ("VIEWER", "Read-only access"),
]

ACTIVITY_TYPES = [
    "LOGIN", "LOGOUT", "FILE_ACCESS", "FILE_DOWNLOAD", "USB_CONNECT",
    "CLOUD_UPLOAD", "EMAIL_EXTERNAL", "PRIVILEGE_CHANGE", "REMOTE_SESSION",
    "DEVICE_CHANGE", "LOCATION_CHANGE",
]

DETECTION_TYPES = [
    "OFF_HOURS_ACCESS", "LATERAL_MOVEMENT", "DORMANT_ACCOUNT_REVIVAL",
    "RESOURCE_SNOOPING", "PRIVILEGE_ESCALATION", "IMPOSSIBLE_TRAVEL",
    "PEER_GROUP_DEVIATION", "SESSION_ANOMALY",
]


def seed():
    print("=" * 60)
    print("SENTINEL UEBA - Database Seed Script")
    print("All data is SYNTHETIC / DEVELOPMENT DATA")
    print("=" * 60)
    print()

    db = SessionLocal()
    try:
        # ── Create Roles ───────────────────────────────────────────────────
        print("[1/7] Creating roles...")
        roles = {}
        for name, description in ROLE_DEFINITIONS:
            existing = db.query(Role).filter(Role.name == name).first()
            if existing:
                roles[name] = existing
                print(f"  ✓ Role '{name}' already exists")
            else:
                role = Role(name=name, description=description)
                db.add(role)
                db.flush()
                roles[name] = role
                print(f"  + Role '{name}' created")

        # ── Create Users ───────────────────────────────────────────────────
        print("\n[2/7] Creating demo users...")
        created_users = []
        for user_data in USERS_DATA:
            existing = db.query(User).filter(User.email == user_data["email"]).first()
            if existing:
                created_users.append(existing)
                print(f"  ✓ User '{user_data['email']}' already exists")
                continue

            user = User(
                name=user_data["name"],
                email=user_data["email"],
                password_hash=hash_password(user_data["password"]),
                department=user_data["department"],
                job_title=user_data["job_title"],
                status="ACTIVE",
            )
            db.add(user)
            db.flush()

            # Assign roles
            for role_name in user_data["roles"]:
                if role_name in roles:
                    user.roles.append(roles[role_name])

            created_users.append(user)
            print(f"  + User '{user_data['email']}' created (roles: {', '.join(user_data['roles'])})")

        db.commit()

        # ── Create Activities ──────────────────────────────────────────────
        print("\n[3/7] Creating sample activities...")
        now = datetime.now(timezone.utc)
        activity_count = 0

        # Generate activities for each non-admin user
        target_users = [u for u in created_users if "ADMIN" not in [r.name for r in u.roles]]

        for user in target_users:
            num_activities = random.randint(15, 40)
            for _ in range(num_activities):
                event_type = random.choice(ACTIVITY_TYPES)
                timestamp = now - timedelta(
                    hours=random.randint(0, 168),
                    minutes=random.randint(0, 59),
                )
                hour = timestamp.hour
                is_off_hours = hour < 6 or hour > 22
                risk = random.uniform(0.0, 0.3)
                if is_off_hours:
                    risk = random.uniform(0.4, 0.9)

                activity = Activity(
                    user_id=user.id,
                    timestamp=timestamp,
                    event_type=event_type,
                    action=f"{event_type.lower().replace('_', ' ')} event",
                    resource=f"resource-{random.randint(100, 999)}",
                    source_ip=f"10.{random.randint(1, 254)}.{random.randint(1, 254)}.{random.randint(1, 254)}",
                    device=f"device-{random.choice(['laptop', 'desktop', 'mobile'])}",
                    location=random.choice(["London, UK", "New York, US", "Singapore, SG", "Remote"]),
                    application=random.choice(["SSO", "VPN", "Email", "Cloud Storage", "Database"]),
                    risk_contribution=round(risk, 4),
                )
                db.add(activity)
                activity_count += 1

        db.commit()
        print(f"  + {activity_count} activities created")

        # ── Create Anomalies ───────────────────────────────────────────────
        print("\n[4/7] Creating sample anomalies...")
        anomaly_count = 0
        anomaly_objects = []

        for user in target_users:
            num_anomalies = random.randint(1, 5)
            for _ in range(num_anomalies):
                det_type = random.choice(DETECTION_TYPES)
                risk_score = round(random.uniform(20, 95), 1)
                anomaly_score = round(random.uniform(0.3, 0.95), 4)
                severity = "LOW"
                if risk_score >= 90:
                    severity = "CRITICAL"
                elif risk_score >= 70:
                    severity = "HIGH"
                elif risk_score >= 40:
                    severity = "MEDIUM"

                anomaly = Anomaly(
                    user_id=user.id,
                    detection_type=det_type,
                    severity=severity,
                    risk_score=risk_score,
                    anomaly_score=anomaly_score,
                    confidence=round(random.uniform(0.6, 0.95), 4),
                    description=f"Detected {det_type.lower().replace('_', ' ')} for user {user.name}",
                    status=random.choice(["OPEN", "OPEN", "IN_REVIEW", "RESOLVED"]),
                    detected_at=now - timedelta(hours=random.randint(1, 72)),
                )
                db.add(anomaly)
                db.flush()
                anomaly_objects.append(anomaly)
                anomaly_count += 1

                # Create risk events for this anomaly
                for signal_type in random.sample(DETECTION_TYPES[:5], min(3, len(DETECTION_TYPES))):
                    rf = RiskEvent(
                        user_id=user.id,
                        anomaly_id=anomaly.id,
                        signal_type=signal_type,
                        signal_value=round(random.uniform(0.1, 1.0), 3),
                        weight=round(random.uniform(0.1, 0.3), 2),
                        contribution=round(random.uniform(0.05, 0.25), 3),
                    )
                    db.add(rf)

        db.commit()
        print(f"  + {anomaly_count} anomalies created")

        # ── Create Investigations ──────────────────────────────────────────
        print("\n[5/7] Creating sample investigations...")
        analyst = next((u for u in created_users if any(r.name == "SECURITY_ANALYST" for r in u.roles)), None)

        investigation_count = 0
        for anomaly in random.sample(anomaly_objects, min(8, len(anomaly_objects))):
            inv = Investigation(
                anomaly_id=anomaly.id,
                assigned_to=analyst.id if analyst else None,
                title=f"Investigation: {anomaly.detection_type.replace('_', ' ').title()}",
                summary=f"Automated investigation for {anomaly.detection_type} anomaly affecting user.",
                status=random.choice(["OPEN", "IN_PROGRESS", "RESOLVED"]),
                priority=random.choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"]),
            )
            db.add(inv)
            db.flush()
            investigation_count += 1

            # Create investigation event
            if analyst:
                event = InvestigationEvent(
                    investigation_id=inv.id,
                    actor_id=analyst.id,
                    action="CREATED",
                    description=f"Investigation created by {analyst.name}",
                )
                db.add(event)

        db.commit()
        print(f"  + {investigation_count} investigations created")

        # ── Create Detection Policies ──────────────────────────────────────
        print("\n[6/7] Creating detection policies...")
        admin_user = next((u for u in created_users if any(r.name == "ADMIN" for r in u.roles)), None)

        policies_data = [
            ("Off-Hours Access Detection", "OFF_HOURS_ACCESS", "Detect resource access outside normal hours", 0.5, "HIGH", True),
            ("Lateral Movement Detection", "LATERAL_MOVEMENT", "Detect sequential authentication across hosts", 0.6, "CRITICAL", True),
            ("Dormant Account Monitoring", "DORMANT_ACCOUNT_REVIVAL", "Detect dormant accounts becoming active", 0.5, "MEDIUM", True),
            ("Privilege Escalation Rules", "PRIVILEGE_ESCALATION", "Detect privilege acquisition outside change windows", 0.7, "CRITICAL", True),
            ("Peer Deviation Monitoring", "PEER_GROUP_DEVIATION", "Detect behaviour diverging from peer group", 0.6, "MEDIUM", True),
            ("Impossible Travel Detection", "IMPOSSIBLE_TRAVEL", "Detect geographically impossible login sequences", 0.65, "HIGH", True),
            ("Resource Enumeration Detection", "RESOURCE_SNOOPING", "Detect rapid enumeration of resources", 0.55, "HIGH", True),
            ("Session Anomaly Detection", "SESSION_ANOMALY", "Detect session replay and fingerprint anomalies", 0.6, "MEDIUM", True),
        ]

        for name, det_type, desc, threshold, severity, enabled in policies_data:
            existing = db.query(DetectionPolicy).filter(DetectionPolicy.name == name).first()
            if existing:
                print(f"  ✓ Policy '{name}' already exists")
                continue

            policy = DetectionPolicy(
                name=name,
                description=desc,
                detection_type=det_type,
                enabled=enabled,
                severity=severity,
                threshold=threshold,
                created_by=admin_user.id if admin_user else None,
                updated_by=admin_user.id if admin_user else None,
            )
            db.add(policy)
            print(f"  + Policy '{name}' created")

        db.commit()
        print(f"  + {len(policies_data)} policies created")

        # ── Summary ────────────────────────────────────────────────────────
        print("\n[7/7] Seed complete!")
        print()
        print("=" * 60)
        print("SEED DATA SUMMARY")
        print("=" * 60)
        print(f"  Users:       {db.query(User).count()}")
        print(f"  Roles:       {db.query(Role).count()}")
        print(f"  Activities:  {db.query(Activity).count()}")
        print(f"  Anomalies:   {db.query(Anomaly).count()}")
        print(f"  Risk Events: {db.query(RiskEvent).count()}")
        print(f"  Investigations: {db.query(Investigation).count()}")
        print(f"  Policies:    {db.query(DetectionPolicy).count()}")
        print()
        print("DEMO CREDENTIALS (SYNTHETIC DATA):")
        print("-" * 40)
        print("  Admin:   admin@sentinel.demo / Admin123!")
        print("  Analyst: sarah.chen@sentinel.demo / Analyst123!")
        print("  Viewer:  viewer@sentinel.demo / Viewer123!")
        print("  Manager: manager@sentinel.demo / Manager123!")
        print()
        print("NOTE: All data is SYNTHETIC / DEVELOPMENT DATA.")
        print("      Do not use these credentials in production.")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"\nError during seeding: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    seed()
