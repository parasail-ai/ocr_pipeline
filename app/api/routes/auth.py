"""Authentication and API key management routes"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApiKey, ApiProfile
from app.db.session import get_db
from app.models.auth import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyList,
    ApiKeyRead,
    ApiProfileCreate,
    ApiProfileList,
    ApiProfileRead,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/profiles", response_model=ApiProfileRead, status_code=status.HTTP_201_CREATED)
async def create_profile(
    payload: ApiProfileCreate,
    db: AsyncSession = Depends(get_db)
) -> ApiProfileRead:
    """Create a new API profile"""
    # Check if email already exists
    stmt = select(ApiProfile).where(ApiProfile.email == payload.email)
    existing = await db.scalar(stmt)
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile with this email already exists"
        )
    
    profile = await AuthService.create_profile(
        name=payload.name,
        email=payload.email,
        db=db
    )
    
    return ApiProfileRead.model_validate(profile)


@router.get("/profiles", response_model=ApiProfileList)
async def list_profiles(
    db: AsyncSession = Depends(get_db)
) -> ApiProfileList:
    """List all API profiles"""
    stmt = select(ApiProfile).order_by(ApiProfile.created_at.desc())
    result = await db.execute(stmt)
    profiles = list(result.scalars().all())
    
    return ApiProfileList(
        items=[ApiProfileRead.model_validate(p) for p in profiles]
    )


@router.get("/profiles/{profile_id}", response_model=ApiProfileRead)
async def get_profile(
    profile_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> ApiProfileRead:
    """Get a specific API profile"""
    profile = await db.get(ApiProfile, profile_id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    return ApiProfileRead.model_validate(profile)


@router.post("/profiles/{profile_id}/keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    profile_id: uuid.UUID,
    payload: ApiKeyCreate,
    db: AsyncSession = Depends(get_db)
) -> ApiKeyCreated:
    """Create a new API key for a profile"""
    # Verify profile exists
    profile = await db.get(ApiProfile, profile_id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    if not profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create API key for inactive profile"
        )
    
    # Create the API key
    key, api_key = await AuthService.create_api_key(
        profile_id=str(profile_id),
        name=payload.name,
        db=db,
        expires_at=payload.expires_at
    )
    
    return ApiKeyCreated(
        key=key,
        key_info=ApiKeyRead.model_validate(api_key)
    )


@router.get("/profiles/{profile_id}/keys", response_model=ApiKeyList)
async def list_profile_keys(
    profile_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> ApiKeyList:
    """List all API keys for a profile"""
    # Verify profile exists
    profile = await db.get(ApiProfile, profile_id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    stmt = (
        select(ApiKey)
        .where(ApiKey.profile_id == profile_id)
        .order_by(ApiKey.created_at.desc())
    )
    result = await db.execute(stmt)
    keys = list(result.scalars().all())
    
    return ApiKeyList(
        items=[ApiKeyRead.model_validate(k) for k in keys]
    )


@router.delete("/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> None:
    """Revoke (deactivate) an API key"""
    api_key = await db.get(ApiKey, key_id)
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    api_key.is_active = False
    await db.commit()
