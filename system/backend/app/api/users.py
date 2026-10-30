from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import hash_password, require_roles
from ..models import User
from ..schemas import UserCreate, UserOut, UserUpdate
from ..services.audit import audit

router = APIRouter(
    prefix="/api/users",
    tags=["users"],
    dependencies=[Depends(require_roles("admin"))],
)


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).order_by(User.id).all()


@router.post("", response_model=UserOut)
def create_user(payload: UserCreate, db: Session = Depends(get_db),
                admin: User = Depends(require_roles("admin"))):
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    if payload.role not in ("admin", "operator", "viewer"):
        raise HTTPException(status_code=400, detail="角色不合法")
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name or payload.username,
        role=payload.role,
        is_active=True,
        approval_status="approved",
        must_change_password=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    audit(db, admin, "create_user", user.username, {"role": user.role})
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db),
                admin: User = Depends(require_roles("admin"))):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.role is not None:
        if payload.role not in ("admin", "operator", "viewer"):
            raise HTTPException(status_code=400, detail="角色不合法")
        if user.id == admin.id and payload.role != "admin":
            raise HTTPException(status_code=400, detail="不能修改自己的管理员角色")
        user.role = payload.role
    if payload.is_active is not None:
        if user.id == admin.id and not payload.is_active:
            raise HTTPException(status_code=400, detail="不能停用自己")
        user.is_active = payload.is_active
        if payload.is_active:
            user.approval_status = "approved"
    db.commit()
    db.refresh(user)
    audit(db, admin, "update_user", user.username, payload.model_dump(exclude_none=True))
    return user


@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db),
                admin: User = Depends(require_roles("admin"))):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除自己")
    db.delete(user)
    db.commit()
    audit(db, admin, "delete_user", user.username)
    return {"ok": True}


@router.post("/{user_id}/approve", response_model=UserOut)
def approve_user(user_id: int, db: Session = Depends(get_db),
                 admin: User = Depends(require_roles("admin"))):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.is_active = True
    user.approval_status = "approved"
    db.commit()
    db.refresh(user)
    audit(db, admin, "approve_user", user.username)
    return user


@router.post("/{user_id}/reject", response_model=UserOut)
def reject_user(user_id: int, db: Session = Depends(get_db),
                admin: User = Depends(require_roles("admin"))):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.is_active = False
    user.approval_status = "rejected"
    db.commit()
    db.refresh(user)
    audit(db, admin, "reject_user", user.username)
    return user


@router.post("/{user_id}/reset-password")
def reset_password(user_id: int, db: Session = Depends(get_db),
                   admin: User = Depends(require_roles("admin"))):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.password_hash = hash_password("12345678")
    user.must_change_password = True
    db.commit()
    audit(db, admin, "reset_password", user.username)
    return {"ok": True, "temporary_password": "12345678"}
