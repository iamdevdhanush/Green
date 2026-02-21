"""Authentication service"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.user import User
from app.schemas.user import UserCreate, TokenPair
from app.core.logging import get_logger

log = get_logger(__name__)


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def create_user(self, data: UserCreate) -> User:
        existing = self.db.execute(
            select(User).where(User.email == data.email)
        ).scalar_one_or_none()

        if existing:
            raise ValueError("Email already registered")

        user = User(
            email=data.email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            role=data.role,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        log.info("user_created", email=data.email, role=data.role)
        return user

    def authenticate(self, email: str, password: str) -> Optional[User]:
        user = self.db.execute(
            select(User).where(User.email == email, User.is_active == True)
        ).scalar_one_or_none()

        if not user or not verify_password(password, user.hashed_password):
            return None

        # Update last login
        user.last_login = datetime.now(timezone.utc)
        self.db.commit()
        return user

    def create_tokens(self, user: User) -> TokenPair:
        access = create_access_token(str(user.id), user.role)
        refresh = create_refresh_token(str(user.id))
        return TokenPair(access_token=access, refresh_token=refresh)

    def refresh_tokens(self, refresh_token: str) -> Optional[TokenPair]:
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None

        user_id = payload.get("sub")
        user = self.db.get(User, uuid.UUID(user_id))
        if not user or not user.is_active:
            return None

        return self.create_tokens(user)

    def get_user_from_token(self, token: str) -> Optional[User]:
        payload = decode_token(token)
        if not payload or payload.get("type") != "access":
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        user = self.db.get(User, uuid.UUID(user_id))
        if not user or not user.is_active:
            return None
        return user
