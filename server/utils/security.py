"""GreenOps Security Dependencies"""
from typing import Optional
import structlog
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from database import AsyncSession, AgentToken, User, get_db
from utils.auth import decode_access_token, hash_agent_token

logger = structlog.get_logger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "Authentication required."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_token", "message": "Token is invalid or expired."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    from sqlalchemy import select
    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "user_not_found", "message": "User not found or inactive."},
        )
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    from database import UserRole
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message": "Admin access required."},
        )
    return current_user


async def get_current_machine(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    from database import Machine
    from sqlalchemy import select
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "Agent token required."},
        )
    raw_token = credentials.credentials
    token_hash = hash_agent_token(raw_token)
    result = await db.execute(
        select(AgentToken).where(AgentToken.token_hash == token_hash, AgentToken.revoked == False)
    )
    agent_token = result.scalar_one_or_none()
    if not agent_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_token", "message": "Agent token is invalid or revoked."},
        )
    result = await db.execute(select(Machine).where(Machine.id == agent_token.machine_id))
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "machine_not_found", "message": "Machine not found."},
        )
    from datetime import datetime, timezone
    agent_token.last_used = datetime.now(timezone.utc)
    return machine
