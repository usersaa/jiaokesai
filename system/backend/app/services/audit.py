from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from ..models import AuditLog, User


def audit(db: Session, user: Optional[User], action: str, target: str = "",
          detail: Optional[dict] = None, ip: str = "") -> None:
    db.add(AuditLog(
        user_id=user.id if user else None,
        username=user.username if user else "",
        action=action,
        target=target,
        detail_json=detail or {},
        ip=ip,
    ))
    db.commit()
