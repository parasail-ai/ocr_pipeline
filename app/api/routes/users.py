import uuid
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.session import get_db
from app.services.auth import AuthService


router = APIRouter(prefix="/users", tags=["users"])


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    is_admin: bool = False


class UserResponse(BaseModel):
    id: str
    email: str
    is_admin: bool
    is_active: bool
    created_at: str
    last_login_at: Optional[str] = None

    @classmethod
    def from_user(cls, user: User) -> "UserResponse":
        return cls(
            id=str(user.id),
            email=user.email,
            is_admin=user.is_admin,
            is_active=user.is_active,
            created_at=user.created_at.isoformat() if user.created_at else "",
            last_login_at=user.last_login_at.isoformat() if user.last_login_at else None
        )


class UsersListResponse(BaseModel):
    items: list[UserResponse]
    total: int


async def require_admin(
    session_token: Optional[str] = Cookie(None)
) -> None:
    """Dependency to check if user is admin."""
    if not AuthService.is_admin(session_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    request: CreateUserRequest,
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """Public signup endpoint for new users."""
    user = await AuthService.create_user(
        db=db,
        email=request.email,
        password=request.password,
        is_admin=False  # New signups are never admin
    )
    
    return UserResponse.from_user(user)


@router.get("", response_model=UsersListResponse)
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin)
) -> UsersListResponse:
    """List all users (admin only)."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    
    return UsersListResponse(
        items=[UserResponse.from_user(user) for user in users],
        total=len(users)
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin)
) -> UserResponse:
    """Create a new user (admin only)."""
    # Check if user already exists
    existing_user = await AuthService.get_user_by_email(db, request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Create user
    user = await AuthService.create_user(
        db=db,
        email=request.email,
        password=request.password,
        is_admin=request.is_admin
    )
    
    return UserResponse.from_user(user)


@router.patch("/{user_id}/toggle-admin", response_model=UserResponse)
async def toggle_admin(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    session_token: Optional[str] = Cookie(None)
) -> UserResponse:
    """Toggle user admin status (admin only)."""
    if not AuthService.is_admin(session_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    # Get current admin user email
    admin_email = AuthService.get_session_user(session_token)
    
    # Get target user
    user = await AuthService.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent admin from removing their own admin status
    if user.email == admin_email and user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove your own admin status"
        )
    
    # Toggle admin status
    updated_user = await AuthService.toggle_admin(db, user_id)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse.from_user(updated_user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    session_token: Optional[str] = Cookie(None)
) -> None:
    """Delete a user (admin only, cannot delete self)."""
    if not AuthService.is_admin(session_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    # Get current admin user email
    admin_email = AuthService.get_session_user(session_token)
    
    # Get target user
    user = await AuthService.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent admin from deleting themselves
    if user.email == admin_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # Delete user
    success = await AuthService.delete_user(db, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
