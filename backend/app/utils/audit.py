import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi import Request


logger = logging.getLogger("sentinel.audit")


def log_audit_event(
    request: Optional[Request],
    actor_id: Optional[str],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """Log a security-sensitive audit event.
    
    This function logs to the structured audit logger.
    In production, this would also write to an audit_events table.
    """
    event_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    
    ip_address = None
    if request:
        ip_address = request.client.host if request.client else None
    
    audit_entry = {
        "event_id": event_id,
        "timestamp": timestamp,
        "actor_id": actor_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "ip_address": ip_address,
        "metadata": metadata or {},
    }
    
    # Log to structured logger
    logger.info(
        f"AUDIT: {action} on {resource_type} by actor {actor_id}",
        extra=audit_entry,
    )
    
    return audit_entry
