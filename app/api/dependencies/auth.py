"""Authentication dependencies for FastAPI"""
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db
from app.services.auth import AuthService
from app.services.api_key_service import authenticate_api_key

security = HTTPBearer(auto_error=False)


def get_current_user(
    session_token: Optional[str] = Cookie(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get the current authenticated user from either session cookie or API key.
    
    Raises 401 if no valid authentication is provided.
    """
    # Try API key authentication first
    if credentials:
        user = authenticate_api_key(db, credentials.credentials)
        if user:
            return user
    
    # Try session authentication
    if session_token:
        email = AuthService.get_session_user(session_token)
        if email:
            user = db.query(User).filter(User.email == email, User.is_active == True).first()
            if user:
                return user
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user_optional(
    session_token: Optional[str] = Cookie(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get the current authenticated user from either session cookie or API key.
    
    Returns None if no valid authentication is provided.
    """
    # Try API key authentication first
    if credentials:
        user = authenticate_api_key(db, credentials.credentials)
        if user:
            return user
    
    # Try session authentication
    if session_token:
        email = AuthService.get_session_user(session_token)
        if email:
            user = db.query(User).filter(User.email == email, User.is_active == True).first()
            if user:
                return user
    
    return None


# Backward compatibility aliases
get_api_key_optional = get_current_user_optional
get_api_key_required = get_current_user
