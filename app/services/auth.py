import hashlib
import secrets
from typing import Optional


class AuthService:
    """Simple authentication service for admin users."""
    
    # Admin credentials (in production, store in database with hashed passwords)
    ADMIN_EMAIL = "matthew.carnali@parasail.io"
    # Hash of "Hqbiscuit51!"
    ADMIN_PASSWORD_HASH = hashlib.sha256("Hqbiscuit51!".encode()).hexdigest()
    
    # Session store (in production, use Redis or database)
    _sessions: dict[str, str] = {}
    
    @classmethod
    def verify_credentials(cls, email: str, password: str) -> bool:
        """Verify email and password against admin credentials."""
        if email != cls.ADMIN_EMAIL:
            return False
        
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        return password_hash == cls.ADMIN_PASSWORD_HASH
    
    @classmethod
    def create_session(cls, email: str) -> str:
        """Create a new session and return session token."""
        session_token = secrets.token_urlsafe(32)
        cls._sessions[session_token] = email
        return session_token
    
    @classmethod
    def get_session_user(cls, session_token: Optional[str]) -> Optional[str]:
        """Get user email from session token."""
        if not session_token:
            return None
        return cls._sessions.get(session_token)
    
    @classmethod
    def is_admin(cls, session_token: Optional[str]) -> bool:
        """Check if session token belongs to admin user."""
        email = cls.get_session_user(session_token)
        return email == cls.ADMIN_EMAIL
    
    @classmethod
    def delete_session(cls, session_token: str) -> None:
        """Delete a session (logout)."""
        cls._sessions.pop(session_token, None)
