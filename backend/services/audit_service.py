from __future__ import annotations
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from backend.models.audit import AuditLog

def log_audit_event(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> AuditLog:
    entry = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        ip_address=ip_address,
        details_json=details
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
