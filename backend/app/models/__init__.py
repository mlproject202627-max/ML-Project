from app.models.user import User, Role
from app.models.activity import Activity
from app.models.anomaly import Anomaly
from app.models.risk_event import RiskEvent
from app.models.investigation import Investigation, InvestigationEvent
from app.models.detection_policy import DetectionPolicy
from app.models.notification import Notification
from app.models.telemetry import TelemetryEvent
from app.models.session import UserSession
from app.models.agent_key import AgentKey
from app.models.banking import (
    Branch, Customer, BankAccount, Transaction,
    LoanApplication, KycCase, PortalDocument, SupportTicket, PortalNotification,
)

# Detection foundation (spec §2)
from app.models.resource import (
    Resource, CLASSIFICATIONS, CLASSIFICATION_RISK_WEIGHT,
    SENSITIVE_CLASSIFICATIONS, classification_rank, is_sensitive,
)
from app.models.device import Device, build_fingerprint
from app.models.usb_event import UsbEvent, USB_ACTIONS
from app.models.baseline import EmployeeBaseline
from app.models.risk_score import RiskScore, level_for_score, RISK_LEVELS, RISK_LEVEL_COLOR
from app.models.audit_log import AuditLog
from app.models.admin_action import AdminAction, ADMIN_ACTIONS

__all__ = [
    "User", "Role",
    "Activity",
    "Anomaly",
    "RiskEvent",
    "Investigation", "InvestigationEvent",
    "DetectionPolicy",
    "Notification",
    "TelemetryEvent",
    "UserSession",
    "AgentKey",
    "Branch", "Customer", "BankAccount", "Transaction",
    "LoanApplication", "KycCase", "PortalDocument", "SupportTicket", "PortalNotification",
    # Detection foundation
    "Resource", "CLASSIFICATIONS", "CLASSIFICATION_RISK_WEIGHT",
    "SENSITIVE_CLASSIFICATIONS", "classification_rank", "is_sensitive",
    "Device", "build_fingerprint",
    "UsbEvent", "USB_ACTIONS",
    "EmployeeBaseline",
    "RiskScore", "level_for_score", "RISK_LEVELS", "RISK_LEVEL_COLOR",
    "AuditLog",
    "AdminAction", "ADMIN_ACTIONS",
]
