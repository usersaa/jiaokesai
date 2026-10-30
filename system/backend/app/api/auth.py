from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import (
    create_token, get_current_user, hash_password, verify_password,
)
from ..models import Setting, User
from ..schemas import ChangePasswordIn, LoginIn, RegisterIn, TokenOut, UserOut
from ..services.audit import audit

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号待审核或已停用")
    user.last_login_at = datetime.utcnow()
    db.commit()
    audit(db, user, "login", user.username, ip=request.client.host if request.client else "")
    return {"token": create_token(user), "user": user}


@router.post("/register", response_model=UserOut)
def register(payload: RegisterIn, request: Request, db: Session = Depends(get_db)):
    setting = db.get(Setting, "self_registration")
    enabled = True if setting is None else bool(setting.value_json)
    if not enabled:
        raise HTTPException(status_code=403, detail="自助注册已关闭")
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name or payload.username,
        role="viewer",
        is_active=False,
        approval_status="pending",
        must_change_password=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    audit(db, None, "register", user.username,
          {"display_name": user.display_name},
          request.client.host if request.client else "")
    return user


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/change-password")
def change_password(payload: ChangePasswordIn,
                    user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    db.commit()
    audit(db, user, "change_password", user.username)
    return {"ok": True}


@router.get("/registration-policy")
def registration_policy(db: Session = Depends(get_db)):
    setting = db.get(Setting, "self_registration")
    return {"enabled": True if setting is None else bool(setting.value_json)}
