"""Authentication and API key management service"""
import hashlib
import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApiKey, ApiProfile


class AuthService:
    """Service for managing API authentication"""

    @staticmethod
    def generate_api_key() -> tuple[str, str, str]:
        """
        Generate a new API key
        
        Returns:
            tuple: (full_key, key_hash, key_prefix)
        """
        # Generate a secure random key
        key = f"ocr_{secrets.token_urlsafe(32)}"
        
        # Create hash for storage
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        
        # Get prefix for identification (first 12 chars)
        key_prefix = key[:12]
        
        return key, key_hash, key_prefix

    @staticmethod
    async def validate_api_key(key: str, db: AsyncSession) -> Optional[ApiProfile]:
        """
        Validate an API key and return the associated profile
        
        Args:
            key: The API key to validate
            db: Database session
            
        Returns:
            ApiProfile if valid, None otherwise
        """
        if not key or not key.startswith("ocr_"):
            return None
        
        # Hash the provided key
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        
        # Look up the key
        stmt = (
            select(ApiKey)
            .where(ApiKey.key_hash == key_hash)
            .where(ApiKey.is_active == True)
        )
        result = await db.execute(stmt)
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            return None
        
        # Check if key is expired
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            return None
        
        # Update last used timestamp
        api_key.last_used_at = datetime.utcnow()
        await db.commit()
        
        # Get the profile
        profile = await db.get(ApiProfile, api_key.profile_id)
        
        if not profile or not profile.is_active:
            return None
        
        return profile

    @staticmethod
    async def create_profile(
        name: str,
        email: str,
        db: AsyncSession
    ) -> ApiProfile:
        """
        Create a new API profile
        
        Args:
            name: Profile name
            email: Profile email
            db: Database session
            
        Returns:
            Created ApiProfile
        """
        profile = ApiProfile(
            name=name,
            email=email,
            is_active=True
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        return profile

    @staticmethod
    async def create_api_key(
        profile_id: str,
        name: str,
        db: AsyncSession,
        expires_at: Optional[datetime] = None
    ) -> tuple[str, ApiKey]:
        """
        Create a new API key for a profile
        
        Args:
            profile_id: UUID of the profile
            name: Name/description for the key
            db: Database session
            expires_at: Optional expiration date
            
        Returns:
            tuple: (plain_text_key, ApiKey object)
        """
        key, key_hash, key_prefix = AuthService.generate_api_key()
        
        api_key = ApiKey(
            profile_id=profile_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=name,
            is_active=True,
            expires_at=expires_at
        )
        
        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)
        
        return key, api_key
