import logging
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.models.auth import ChangePasswordRequest, ChangePasswordResponse
from app.services.auth import AuthService
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    success: bool
    message: str
    is_admin: bool


class SessionResponse(BaseModel):
    is_authenticated: bool
    is_admin: bool
    email: Optional[str] = None


@router.post("/login", response_model=LoginResponse)
async def login(
    credentials: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
) -> LoginResponse:
    """Login endpoint."""
    
    # Verify credentials
    if not await AuthService.verify_credentials(db, credentials.email, credentials.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Create session
    session_token = await AuthService.create_session(db, credentials.email)
    
    # Set session cookie (httponly for security)
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        max_age=86400 * 7,  # 7 days
        samesite="lax"
    )
    
    logger.info(f"Login successful: {credentials.email}")
    
    # Check if user is admin
    is_admin = AuthService.is_admin(session_token)
    
    return LoginResponse(
        success=True,
        message="Login successful",
        is_admin=is_admin
    )


@router.post("/logout")
async def logout(
    response: Response,
    session_token: Optional[str] = Cookie(None)
) -> dict:
    """Logout endpoint."""
    
    if session_token:
        AuthService.delete_session(session_token)
    
    # Clear session cookie
    response.delete_cookie(key="session_token")
    
    return {"success": True, "message": "Logged out successfully"}


@router.get("/session", response_model=SessionResponse)
async def get_session(
    session_token: Optional[str] = Cookie(None)
) -> SessionResponse:
    """Check current session status."""
    
    if not session_token:
        return SessionResponse(
            is_authenticated=False,
            is_admin=False
        )
    
    email = AuthService.get_session_user(session_token)
    
    if not email:
        return SessionResponse(
            is_authenticated=False,
            is_admin=False
        )
    
    is_admin = AuthService.is_admin(session_token)
    
    return SessionResponse(
        is_authenticated=True,
        is_admin=is_admin,
        email=email if is_admin else None
    )


@router.post("/change-password", response_model=ChangePasswordResponse)
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
) -> ChangePasswordResponse:
    """
    Change the password for the authenticated user.
    
    Requires the current password for verification.
    """
    # Verify current password
    if not pwd_context.verify(password_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )
    
    # Check that new password is different
    if pwd_context.verify(password_data.new_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )
    
    # Hash new password
    new_password_hash = pwd_context.hash(password_data.new_password)
    
    # Update password in database
    current_user.password_hash = new_password_hash
    current_user.password_changed_at = datetime.utcnow()
    db.commit()
    
    logger.info(f"Password changed successfully for user: {current_user.email}")
    
    return ChangePasswordResponse(
        message="Password changed successfully",
        changed_at=current_user.password_changed_at
    )
