"""Pydantic models for authentication"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class ChangePasswordRequest(BaseModel):
    """Request model for changing password"""
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=100)
    
    @field_validator('new_password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class ChangePasswordResponse(BaseModel):
    """Response model for password change"""
    message: str
    changed_at: datetime


class UserApiKeyCreate(BaseModel):
    """Request model for creating a user API key"""
    name: str = Field(..., min_length=1, max_length=255, description="Name/description for the API key")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration date")


class UserApiKeyRead(BaseModel):
    """Response model for user API key (without the actual key)"""
    id: uuid.UUID
    user_id: uuid.UUID
    key_prefix: str
    name: str
    is_active: bool
    last_used_at: Optional[datetime]
    created_at: datetime
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserApiKeyCreated(BaseModel):
    """Response model when a new API key is created (includes the actual key)"""
    key: str
    key_info: UserApiKeyRead
    message: str = "Store this key securely - it will not be shown again!"


class UserApiKeyUpdate(BaseModel):
    """Request model for updating API key name"""
    name: str = Field(..., min_length=1, max_length=255)


class UserApiKeyList(BaseModel):
    """List of user API keys"""
    items: list[UserApiKeyRead]
    total: int
