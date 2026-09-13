"""Development seed script for Sentinel backend.

Creates demo accounts and synthetic data for testing.
All data is clearly DEMO DATA - not real security events.
"""
import uuid
import random
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine, Base
from app.core.security import hash_password
from app.models.user import User, Role, user_roles
from app.models.activity import Activity
from app.models.anomaly import Anomaly
from app.models.risk_event import RiskEvent
from app.models.investigation import Investigation, InvestigationEvent
from app.models.detection_policy import DetectionPolicy
from app.models.notification import Notification


DEMO_DEPARTMENTS = ["Engineering", "Finance", "IT Ops", "Sales", "HR", "Legal", "Product"]
DEMO_EVENT_TYPES = ["LOGIN", "FILE_ACCESS", "DATABASE_ACCESS", "EMAIL_ACCESS", "PRIVILEGE_CHANGE", "APPLICATION_ACCESS", "NETWORK_ACTIVITY", "AUTHENTICATION_EVENT"]
DEMO_DETECTION_TYPES = ["OFF_HOURS_ACCESS", "LATERAL_MOVEMENT", "DORMANT_ACCOUNT_REVIVAL", "RESOURCE_SNOOPING", "PRIVILEGE_ESCALATION", "IMPOSSIBLE_TRAVEL", "PEER_GROUP_DEVIATION", "SESSION_ANOMALY"]
DEMO_SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
DEMO_RISK_SIGNALS = ["OFF_HOURS_ACCESS", "PEER_GROUP_DEVIATION", "PRIVILEGE_ESCALATION", "RESOURCE_ACCESS", "LOCATION_ANOMALY", "SESSION_BEHAVIOR"]


def seed_roles(db: Session):
    """Create RBAC roles."""
    roles = [
        ("ADMIN", "Full system access"),
        ("SECURITY_MANAGER", "View all security data, manage investigations"),
        ("SECURITY_ANALYST", "View anomalies, investigate threats"),
        ("VIEWER", "Read-only dashboard access"),
    ]
    
    role_objects = {}
    for name, description in roles:
        existing = db.query(Role).filter(Role.name == name).first()
        if not existing:
            role = Role(name=name, description=description)
            db.add(role)
            db.flush()
            role_objects[name] = role
        else:
            role_objects[name] = existing
    
    db.commit()
    return role_objects


def seed_users(db: Session, roles: dict):
    """Create demo user accounts."""
    users_data = [
        {
            "name": "Admin User",
            "email": "admin@sentinel.demo",
            "password": "Admin123!",
            "department": "IT Ops",
            "job_title": "System Administrator",
            "role": "ADMIN",
        },
        {
            "name": "Sarah Chen",
            "email": "sarah.chen@sentinel.demo",
            "password": "Analyst123!",
            "department": "Security",
            "job_title": "Security Analyst",
            "role": "SECURITY_ANALYST",
        },
        {
            "name": "James Wilson",
            "email": "james.wilson@sentinel.demo",
            "password": "Manager123!",
            "department": "Security",
            "job_title": "Security Manager",
            "role": "SECURITY_MANAGER",
        },
        {
            "name": "Viewer User",
            "email": "viewer@sentinel.demo",
            "password": "Viewer123!",
            "department": "Executive",
            "job_title": "Executive Viewer",
            "role": "VIEWER",
        },
    ]
    
    user_objects = []
    for data in users_data:
        existing = db.query(User).filter(User.email == data["email"]).first()
        if not existing:
            user = User(
                name=data["name"],
                email=data["email"],
                password_hash=hash_password(data["password"]),
                department=data["department"],
                job_title=data["job_title"],
                status="ACTIVE",
            )
            db.add(user)
            db.flush()
            
            # Assign role
            role = roles.get(data["role"])
            if role:
                db.execute(user_roles.insert().values(user_id=user.id, role_id=role.id))
            
            user_objects.append(user)
        else:
            user_objects.append(existing)
    
    db.commit()
    return user_objects


def seed_activities(db: Session, users: list):
    """Create synthetic activity events."""
    now = datetime.now(timezone.utc)
    
    for user in users:
        for i in range(random.randint(20, 50)):
            hours_ago = random.randint(0, 168)  # Last 7 days
            timestamp = now - timedelta(hours=hours_ago)
            
            activity = Activity(
                user_id=user.id,
                timestamp=timestamp,
                event_type=random.choice(DEMO_EVENT_TYPES),
                action=f"Accessed {random.choice(['file', 'database', 'email', 'application'])}",
                resource=f"resource-{random.randint(1000, 9999)}",
                source_ip=f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}",
                device=f"WORKSTATION-{random.randint(1, 50):03d}",
                location=random.choice(["London, UK", "New York, US", "Singapore, SG", "Tokyo, JP"]),
                application=random.choice(["Outlook", "Salesforce", "GitHub", "Jira", "Confluence"]),
                metadata={"demo": True},
                risk_contribution=round(random.uniform(0, 0.3), 3),
            )
            db.add(activity)
    
    db.commit()


def seed_anomalies(db: Session, users: list):
    """Create synthetic anomalies."""
    now = datetime.now(timezone.utc)
    anomalies_created = []
    
    for user in users:
        for i in range(random.randint(1, 5)):
            hours_ago = random.randint(0, 72)
            detected_at = now - timedelta(hours=hours_ago)
            
            severity = random.choice(DEMO_SEVERITIES)
            risk_score = {
                "CRITICAL": random.uniform(85, 100),
                "HIGH": random.uniform(70, 84),
                "MEDIUM": random.uniform(50, 69),
                "LOW": random.uniform(0, 49),
            }[severity]
            
            anomaly = Anomaly(
                user_id=user.id,
                detection_type=random.choice(DEMO_DETECTION_TYPES),
                severity=severity,
                risk_score=round(risk_score, 1),
                anomaly_score=round(risk_score / 100, 3),
                confidence=round(random.uniform(0.6, 0.99), 2),
                description=f"Demo: {random.choice(DEMO_DETECTION_TYPES).replace('_', ' ').title()} detected for {user.name}",
                status=random.choice(["OPEN", "IN_REVIEW", "RESOLVED"]),
                detected_at=detected_at,
            )
            db.add(anomaly)
            db.flush()
            anomalies_created.append(anomaly)
            
            # Create risk events for this anomaly
            for signal_type in random.sample(DEMO_RISK_SIGNALS, k=random.randint(2, 4)):
                signal_value = round(random.uniform(0.1, 1.0), 3)
                weight = round(random.uniform(0.05, 0.3), 2)
                contribution = round(signal_value * weight, 3)
                
                risk_event = RiskEvent(
                    user_id=user.id,
                    anomaly_id=anomaly.id,
                    signal_type=signal_type,
                    signal_value=signal_value,
                    weight=weight,
                    contribution=contribution,
                )
                db.add(risk_event)
    
    db.commit()
    return anomalies_created


def seed_investigations(db: Session, anomalies: list, users: list):
    """Create synthetic investigations."""
    analysts = [u for u in users if u.name != "Viewer User"]
    
    for anomaly in anomalies[:5]:
        if random.random() > 0.5:
            continue
            
        assigned_to = random.choice(analysts).id if analysts else None
        investigation = Investigation(
            anomaly_id=anomaly.id,
            assigned_to=assigned_to,
            title=f"Investigation: {anomaly.detection_type.replace('_', ' ').title()}",
            summary=f"Demo investigation for {anomaly.severity.lower()} severity anomaly",
            status=random.choice(["OPEN", "ASSIGNED", "IN_PROGRESS"]),
            priority=anomaly.severity,
        )
        db.add(investigation)
        db.flush()
        
        event = InvestigationEvent(
            investigation_id=investigation.id,
            actor_id=assigned_to,
            action="CREATED",
            description="Investigation created by system",
        )
        db.add(event)
    
    db.commit()


def seed_policies(db: Session, users: list):
    """Create detection policies."""
    policies = [
        ("Off-hours Access", "OFF_HOURS_ACCESS", "Detect access outside normal working hours", 0.7),
        ("Lateral Movement", "LATERAL_MOVEMENT", "Detect unauthorized lateral movement", 0.8),
        ("Impossible Travel", "IMPOSSIBLE_TRAVEL", "Detect impossible travel between locations", 0.9),
        ("Privilege Escalation", "PRIVILEGE_ESCALATION", "Detect unauthorized privilege escalation", 0.75),
        ("Dormant Account", "DORMANT_ACCOUNT_REVIVAL", "Detect dormant account revival", 0.65),
        ("Peer Deviation", "PEER_GROUP_DEVIATION", "Detect behavior deviating from peer group", 0.6),
        ("Resource Snooping", "RESOURCE_SNOOPING", "Detect excessive resource access", 0.7),
        ("Session Anomaly", "SESSION_ANOMALY", "Detect anomalous session behavior", 0.65),
    ]
    
    admin = next((u for u in users if u.name == "Admin User"), users[0])
    
    for name, detection_type, description, threshold in policies:
        existing = db.query(DetectionPolicy).filter(
            DetectionPolicy.detection_type == detection_type
        ).first()
        
        if not existing:
            policy = DetectionPolicy(
                name=name,
                description=description,
                detection_type=detection_type,
                enabled=True,
                severity="MEDIUM",
                threshold=threshold,
                created_by=admin.id,
                updated_by=admin.id,
            )
            db.add(policy)
    
    db.commit()


def seed_notifications(db: Session, users: list, anomalies: list):
    """Create sample notifications."""
    for user in users[:2]:
        for anomaly in anomalies[:3]:
            notification = Notification(
                user_id=user.id,
                type="CRITICAL_ANOMALY",
                title=f"New {anomaly.severity.lower()} anomaly detected",
                message=f"A {anomaly.severity.lower()} severity anomaly was detected",
                related_anomaly_id=anomaly.id,
                read=random.choice([True, False]),
            )
            db.add(notification)
    
    db.commit()


def run_seed():
    """Run the complete seed process."""
    print("🌱 Seeding Sentinel database with DEMO DATA...")
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        print("  Creating roles...")
        roles = seed_roles(db)
        
        print("  Creating users...")
        users = seed_users(db, roles)
        
        print("  Creating activities...")
        seed_activities(db, users)
        
        print("  Creating anomalies...")
        anomalies = seed_anomalies(db, users)
        
        print("  Creating investigations...")
        seed_investigations(db, anomalies, users)
        
        print("  Creating policies...")
        seed_policies(db, users)
        
        print("  Creating notifications...")
        seed_notifications(db, users, anomalies)
        
        print("\n✅ Seed complete!")
        print("\n📋 Demo Accounts:")
        print("  Admin:    admin@sentinel.demo / Admin123!")
        print("  Analyst:  sarah.chen@sentinel.demo / Analyst123!")
        print("  Manager:  james.wilson@sentinel.demo / Manager123!")
        print("  Viewer:   viewer@sentinel.demo / Viewer123!")
        print("\n⚠️  These are DEMO credentials for development only.")
        
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
