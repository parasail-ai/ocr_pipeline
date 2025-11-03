"""Service for generating and managing user API keys."""
import secrets
import hashlib
from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.db.models import UserApiKey, User

# Use bcrypt for hashing API keys
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_api_key() -> tuple[str, str, str]:
    """
    Generate a new API key.
    
    Returns:
        tuple: (full_key, key_hash, key_prefix)
            - full_key: The complete API key to show to user (only once)
            - key_hash: Bcrypt hash of the key for storage
            - key_prefix: First 8 characters for identification
    """
    # Generate a random 32-byte key and encode as hex
    random_bytes = secrets.token_bytes(32)
    key_string = random_bytes.hex()
    
    # Format: pk_live_<64 hex chars>
    full_key = f"pk_live_{key_string}"
    
    # Hash the key for storage
    key_hash = pwd_context.hash(full_key)
    
    # Store prefix for identification (first 12 chars: pk_live_xxxx)
    key_prefix = full_key[:12]
    
    return full_key, key_hash, key_prefix


def verify_api_key(plain_key: str, key_hash: str) -> bool:
    """
    Verify an API key against its hash.
    
    Args:
        plain_key: The plain text API key
        key_hash: The stored bcrypt hash
        
    Returns:
        bool: True if key matches hash
    """
    return pwd_context.verify(plain_key, key_hash)


def create_api_key(
    db: Session,
    user_id: uuid.UUID,
    name: str,
    expires_at: Optional[datetime] = None
) -> tuple[UserApiKey, str]:
    """
    Create a new API key for a user.
    
    Args:
        db: Database session
        user_id: User UUID
        name: Name/description for the key
        expires_at: Optional expiration date
        
    Returns:
        tuple: (UserApiKey model, plain_key_string)
    """
    full_key, key_hash, key_prefix = generate_api_key()
    
    api_key = UserApiKey(
        user_id=user_id,
        name=name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        is_active=True,
        expires_at=expires_at
    )
    
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    
    return api_key, full_key


def get_user_api_keys(db: Session, user_id: uuid.UUID) -> list[UserApiKey]:
    """Get all API keys for a user."""
    return db.query(UserApiKey).filter(
        UserApiKey.user_id == user_id
    ).order_by(UserApiKey.created_at.desc()).all()


def get_api_key_by_id(db: Session, key_id: uuid.UUID, user_id: uuid.UUID) -> Optional[UserApiKey]:
    """Get a specific API key by ID for a user."""
    return db.query(UserApiKey).filter(
        UserApiKey.id == key_id,
        UserApiKey.user_id == user_id
    ).first()


def revoke_api_key(db: Session, key_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """
    Revoke (deactivate) an API key.
    
    Args:
        db: Database session
        key_id: API key UUID
        user_id: User UUID (for security)
        
    Returns:
        bool: True if key was revoked
    """
    api_key = get_api_key_by_id(db, key_id, user_id)
    if api_key:
        api_key.is_active = False
        db.commit()
        return True
    return False


def delete_api_key(db: Session, key_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """
    Permanently delete an API key.
    
    Args:
        db: Database session
        key_id: API key UUID
        user_id: User UUID (for security)
        
    Returns:
        bool: True if key was deleted
    """
    api_key = get_api_key_by_id(db, key_id, user_id)
    if api_key:
        db.delete(api_key)
        db.commit()
        return True
    return False


def update_api_key_name(db: Session, key_id: uuid.UUID, user_id: uuid.UUID, new_name: str) -> Optional[UserApiKey]:
    """Update the name of an API key."""
    api_key = get_api_key_by_id(db, key_id, user_id)
    if api_key:
        api_key.name = new_name
        db.commit()
        db.refresh(api_key)
        return api_key
    return None


def authenticate_api_key(db: Session, plain_key: str) -> Optional[User]:
    """
    Authenticate a user via API key.
    
    Args:
        db: Database session
        plain_key: The plain text API key from request
        
    Returns:
        User object if authentication successful, None otherwise
    """
    if not plain_key or not plain_key.startswith("pk_live_"):
        return None
    
    # Get the prefix for quick lookup
    key_prefix = plain_key[:12]
    
    # Find all keys with this prefix (should be very few, ideally 1)
    potential_keys = db.query(UserApiKey).filter(
        UserApiKey.key_prefix == key_prefix,
        UserApiKey.is_active == True
    ).all()
    
    # Verify against each potential key
    for api_key in potential_keys:
        if verify_api_key(plain_key, api_key.key_hash):
            # Check if key is expired
            if api_key.expires_at and api_key.expires_at < datetime.utcnow():
                continue
            
            # Update last used timestamp
            api_key.last_used_at = datetime.utcnow()
            db.commit()
            
            # Return the user
            user = db.query(User).filter(User.id == api_key.user_id).first()
            return user if user and user.is_active else None
    
    return None
