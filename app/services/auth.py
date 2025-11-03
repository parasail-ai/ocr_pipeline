import hashlib
import secrets
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


class AuthService:
    """Authentication service with database-backed user management."""
    
    # Hardcoded admin credentials as fallback
    ADMIN_EMAIL = "matthew.carnali@parasail.io"
    ADMIN_PASSWORD_HASH = hashlib.sha256("Hqbiscuit51!".encode()).hexdigest()
    
    # Session store (in production, use Redis or database)
    _sessions: dict[str, dict] = {}
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using SHA256."""
        return hashlib.sha256(password.encode()).hexdigest()
    
    @classmethod
    async def create_user(
        cls, 
        db: AsyncSession, 
        email: str, 
        password: str, 
        is_admin: bool = False
    ) -> User:
        """Create a new user in the database."""
        password_hash = cls.hash_password(password)
        user = User(
            id=uuid.uuid4(),
            email=email,
            password_hash=password_hash,
            is_admin=is_admin,
            is_active=True,
            created_at=datetime.utcnow()
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user
    
    @classmethod
    async def get_user_by_email(cls, db: AsyncSession, email: str) -> Optional[User]:
        """Get a user by email."""
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()
    
    @classmethod
    async def get_user_by_id(cls, db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
        """Get a user by ID."""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    
    @classmethod
    async def update_user(
        cls, 
        db: AsyncSession, 
        user_id: uuid.UUID, 
        **kwargs
    ) -> Optional[User]:
        """Update a user's fields."""
        user = await cls.get_user_by_id(db, user_id)
        if not user:
            return None
        
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        await db.commit()
        await db.refresh(user)
        return user
    
    @classmethod
    async def delete_user(cls, db: AsyncSession, user_id: uuid.UUID) -> bool:
        """Delete a user from the database."""
        user = await cls.get_user_by_id(db, user_id)
        if not user:
            return False
        
        await db.delete(user)
        await db.commit()
        return True
    
    @classmethod
    async def toggle_admin(cls, db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
        """Toggle a user's admin status."""
        user = await cls.get_user_by_id(db, user_id)
        if not user:
            return None
        
        user.is_admin = not user.is_admin
        await db.commit()
        await db.refresh(user)
        return user
    
    @classmethod
    async def verify_credentials(cls, db: AsyncSession, email: str, password: str) -> bool:
        """Verify email and password. Check database first, then fallback to hardcoded admin."""
        password_hash = cls.hash_password(password)
        
        # Check database first
        user = await cls.get_user_by_email(db, email)
        if user and user.is_active:
            is_valid = user.password_hash == password_hash
            if is_valid:
                # Update last login
                user.last_login_at = datetime.utcnow()
                await db.commit()
            return is_valid
        
        # Fallback to hardcoded admin
        if email == cls.ADMIN_EMAIL and password_hash == cls.ADMIN_PASSWORD_HASH:
            return True
        
        return False
    
    @classmethod
    async def create_session(cls, db: AsyncSession, email: str) -> str:
        """Create a new session and return session token."""
        session_token = secrets.token_urlsafe(32)
        
        # Check if user is in database
        user = await cls.get_user_by_email(db, email)
        is_admin = user.is_admin if user else (email == cls.ADMIN_EMAIL)
        user_id = str(user.id) if user else None
        
        cls._sessions[session_token] = {
            "email": email,
            "is_admin": is_admin,
            "user_id": user_id
        }
        return session_token
    
    @classmethod
    def get_session_user(cls, session_token: Optional[str]) -> Optional[str]:
        """Get user email from session token."""
        if not session_token:
            return None
        session = cls._sessions.get(session_token)
        return session["email"] if session else None
    
    @classmethod
    def is_admin(cls, session_token: Optional[str]) -> bool:
        """Check if session token belongs to admin user."""
        if not session_token:
            return False
        session = cls._sessions.get(session_token)
        return session.get("is_admin", False) if session else False
    
    @classmethod
    def delete_session(cls, session_token: str) -> None:
        """Delete a session (logout)."""
        cls._sessions.pop(session_token, None)
    
    @classmethod
    def get_user_from_session(cls, session_token: Optional[str]) -> Optional[dict]:
        """Get user info dict from session token."""
        if not session_token:
            return None
        session = cls._sessions.get(session_token)
        if not session:
            return None
        
        email = session["email"]
        return {
            "email": email,
            "username": email.split("@")[0],
            "is_admin": session.get("is_admin", False),
            "user_id": session.get("user_id")
        }
