"""FastAPI dependency that authenticates endpoint agents via X-Agent-Key.

Agents are trusted to report telemetry for the user whose machine they run on:
the key maps 1:1 to a user. A bootstrap shared key (settings.AGENT_API_KEY)
resolves to any user id passed as X-Agent-User — handy for quick tests.
"""
from datetime import datetime, timezone

from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.models.agent_key import AgentKey, generate_agent_key
from app.models.user import User


def _hash_key(raw_key: str) -> str:
    """Fast, deterministic hash for lookup (keys are high-entropy, not passwords)."""
    import hashlib
    return hashlib.sha256(raw_key.encode()).hexdigest()


def get_agent_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    raw_key = request.headers.get("x-agent-key")
    if not raw_key:
        raise HTTPException(status_code=401, detail="Missing X-Agent-Key header")

    key_hash = _hash_key(raw_key)
    agent_key = db.query(AgentKey).filter(AgentKey.key_hash == key_hash, AgentKey.active.is_(True)).first()

    if agent_key:
        user = db.query(User).filter(User.id == agent_key.user_id).first()
        if not user or user.status != "ACTIVE":
            raise HTTPException(status_code=403, detail="Agent's mapped user is not active")
        agent_key.last_used_at = datetime.now(timezone.utc)
        db.commit()
        return user

    # Bootstrap shared key fallback (optional, for testing before keys are issued)
    if settings.AGENT_API_KEY and raw_key == settings.AGENT_API_KEY:
        user_id = request.headers.get("x-agent-user")
        if not user_id:
            raise HTTPException(status_code=400, detail="X-Agent-User header required with the bootstrap key")
        user = db.query(User).filter(User.id == user_id).first()
        if not user or user.status != "ACTIVE":
            raise HTTPException(status_code=403, detail="X-Agent-User does not reference an active user")
        return user

    raise HTTPException(status_code=401, detail="Invalid agent key")


def issue_agent_key(db: Session, *, label: str, user_id: str, created_by) -> tuple[AgentKey, str]:
    """Create a hashed agent key; returns (row, raw_key_shown_once)."""
    raw_key = generate_agent_key()
    row = AgentKey(
        key_hash=_hash_key(raw_key),
        label=label,
        user_id=user_id,
        created_by=created_by,
        active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, raw_key
