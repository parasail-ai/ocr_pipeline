"""Pydantic models for authentication"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class ApiProfileCreate(BaseModel):
    """Request model for creating an API profile"""
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr


class ApiProfileRead(BaseModel):
    """Response model for API profile"""
    id: uuid.UUID
    name: str
    email: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApiKeyCreate(BaseModel):
    """Request model for creating an API key"""
    name: str = Field(..., min_length=1, max_length=255)
    expires_at: Optional[datetime] = None


class ApiKeyRead(BaseModel):
    """Response model for API key (without the actual key)"""
    id: uuid.UUID
    profile_id: uuid.UUID
    key_prefix: str
    name: str
    is_active: bool
    last_used_at: Optional[datetime]
    created_at: datetime
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True


class ApiKeyCreated(BaseModel):
    """Response model when a new API key is created (includes the actual key)"""
    key: str
    key_info: ApiKeyRead


class ApiProfileList(BaseModel):
    """List of API profiles"""
    items: list[ApiProfileRead]


class ApiKeyList(BaseModel):
    """List of API keys"""
    items: list[ApiKeyRead]
