"""Authentication endpoints"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.auth_service import AuthService
from app.schemas.user import (
    UserCreate,
    UserResponse,
    TokenPair,
    LoginRequest,
    RefreshRequest,
)
from app.models.audit_log import AuditLog
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
def register(
    data: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Register a new user (first user becomes admin)."""
    from sqlalchemy import select, func
    from app.models.user import User as UserModel

    user_count = db.execute(select(func.count()).select_from(UserModel)).scalar()
    if user_count == 0:
        data.role = "admin"  # First user is always admin

    svc = AuthService(db)
    try:
        user = svc.create_user(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    audit = AuditLog(
        user_id=user.id,
        action="user_registered",
        resource_type="user",
        resource_id=str(user.id),
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()
    return user


@router.post("/login", response_model=TokenPair)
def login(
    data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    svc = AuthService(db)
    user = svc.authenticate(data.email, data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    audit = AuditLog(
        user_id=user.id,
        action="user_login",
        resource_type="user",
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()

    return svc.create_tokens(user)


@router.post("/refresh", response_model=TokenPair)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)):
    svc = AuthService(db)
    tokens = svc.refresh_tokens(data.refresh_token)
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    return tokens


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user
