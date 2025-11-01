"""Authentication dependencies for FastAPI"""
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApiProfile
from app.db.session import get_db
from app.services.auth import AuthService

security = HTTPBearer(auto_error=False)


async def get_api_key_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[ApiProfile]:
    """
    Optional API key authentication - returns profile if valid key provided, None otherwise
    """
    if not credentials:
        return None
    
    profile = await AuthService.validate_api_key(credentials.credentials, db)
    return profile


async def get_api_key_required(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    db: AsyncSession = Depends(get_db)
) -> ApiProfile:
    """
    Required API key authentication - raises 401 if no valid key provided
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    profile = await AuthService.validate_api_key(credentials.credentials, db)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return profile
