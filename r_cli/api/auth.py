"""
Authentication module for R CLI API.

Provides:
- JWT token generation and validation
- API key management
- User authentication
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# Security configuration
SECRET_KEY = os.getenv("R_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
API_KEY_LENGTH = 32

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# ============================================================================
# Models
# ============================================================================


class Token(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """Data extracted from JWT token."""

    sub: str  # User ID or API key ID
    username: Optional[str] = None
    scopes: list[str] = []
    exp: Optional[datetime] = None


class APIKey(BaseModel):
    """API key model."""

    key_id: str
    key_hash: str
    name: str
    scopes: list[str]
    created_at: datetime
    last_used: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: bool = True


class User(BaseModel):
    """User model for authentication."""

    user_id: str
    username: str
    password_hash: str
    scopes: list[str] = ["read"]
    is_active: bool = True
    created_at: datetime = datetime.now()


# ============================================================================
# Storage (File-based for simplicity)
# ============================================================================


class AuthStorage:
    """Simple file-based storage for auth data."""

    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = Path(storage_dir or os.path.expanduser("~/.r-cli/auth"))
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.users_file = self.storage_dir / "users.json"
        self.api_keys_file = self.storage_dir / "api_keys.json"
        self._init_storage()

    def _init_storage(self):
        """Initialize storage files if they don't exist."""
        if not self.users_file.exists():
            self._save_users({})
        if not self.api_keys_file.exists():
            self._save_api_keys({})

    def _load_users(self) -> dict[str, dict]:
        """Load users from file."""
        try:
            with open(self.users_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _save_users(self, users: dict[str, dict]):
        """Save users to file."""
        with open(self.users_file, "w") as f:
            json.dump(users, f, indent=2, default=str)

    def _load_api_keys(self) -> dict[str, dict]:
        """Load API keys from file."""
        try:
            with open(self.api_keys_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _save_api_keys(self, keys: dict[str, dict]):
        """Save API keys to file."""
        with open(self.api_keys_file, "w") as f:
            json.dump(keys, f, indent=2, default=str)

    def get_user(self, username: str) -> Optional[User]:
        """Get user by username."""
        users = self._load_users()
        if username in users:
            return User(**users[username])
        return None

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        users = self._load_users()
        for user_data in users.values():
            if user_data.get("user_id") == user_id:
                return User(**user_data)
        return None

    def create_user(self, username: str, password: str, scopes: list[str] | None = None) -> User:
        """Create a new user."""
        users = self._load_users()
        if username in users:
            raise ValueError(f"User {username} already exists")

        user = User(
            user_id=secrets.token_urlsafe(16),
            username=username,
            password_hash=pwd_context.hash(password),
            scopes=scopes or ["read"],
            created_at=datetime.now(),
        )
        users[username] = user.model_dump()
        self._save_users(users)
        return user

    def delete_user(self, username: str) -> bool:
        """Delete a user."""
        users = self._load_users()
        if username in users:
            del users[username]
            self._save_users(users)
            return True
        return False

    def get_api_key(self, key_id: str) -> Optional[APIKey]:
        """Get API key by ID."""
        keys = self._load_api_keys()
        if key_id in keys:
            return APIKey(**keys[key_id])
        return None

    def get_api_key_by_hash(self, key_hash: str) -> Optional[APIKey]:
        """Get API key by hash."""
        keys = self._load_api_keys()
        for key_data in keys.values():
            if key_data.get("key_hash") == key_hash:
                return APIKey(**key_data)
        return None

    def create_api_key(
        self,
        name: str,
        scopes: list[str] | None = None,
        expires_in_days: Optional[int] = None,
    ) -> tuple[str, APIKey]:
        """Create a new API key. Returns (raw_key, APIKey)."""
        keys = self._load_api_keys()

        # Generate raw key
        raw_key = secrets.token_urlsafe(API_KEY_LENGTH)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_id = secrets.token_urlsafe(8)

        expires_at = None
        if expires_in_days:
            expires_at = datetime.now() + timedelta(days=expires_in_days)

        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            name=name,
            scopes=scopes or ["read"],
            created_at=datetime.now(),
            expires_at=expires_at,
        )

        keys[key_id] = api_key.model_dump()
        self._save_api_keys(keys)

        return raw_key, api_key

    def update_api_key_last_used(self, key_id: str):
        """Update last_used timestamp for an API key."""
        keys = self._load_api_keys()
        if key_id in keys:
            keys[key_id]["last_used"] = datetime.now().isoformat()
            self._save_api_keys(keys)

    def revoke_api_key(self, key_id: str) -> bool:
        """Revoke an API key."""
        keys = self._load_api_keys()
        if key_id in keys:
            keys[key_id]["is_active"] = False
            self._save_api_keys(keys)
            return True
        return False

    def delete_api_key(self, key_id: str) -> bool:
        """Delete an API key."""
        keys = self._load_api_keys()
        if key_id in keys:
            del keys[key_id]
            self._save_api_keys(keys)
            return True
        return False

    def list_api_keys(self) -> list[APIKey]:
        """List all API keys (without revealing hashes)."""
        keys = self._load_api_keys()
        return [APIKey(**k) for k in keys.values()]


# Global storage instance
_storage: Optional[AuthStorage] = None


def get_storage() -> AuthStorage:
    """Get or create auth storage."""
    global _storage
    if _storage is None:
        _storage = AuthStorage()
    return _storage


# ============================================================================
# JWT Token Functions
# ============================================================================


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    now = datetime.now(tz=None)  # Use local time for JWT
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> TokenData:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return TokenData(
            sub=payload.get("sub"),
            username=payload.get("username"),
            scopes=payload.get("scopes", []),
            exp=datetime.fromtimestamp(payload.get("exp", 0)),
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ============================================================================
# Authentication Functions
# ============================================================================


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def authenticate_user(username: str, password: str) -> Optional[User]:
    """Authenticate a user with username and password."""
    storage = get_storage()
    user = storage.get_user(username)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    if not user.is_active:
        return None
    return user


def validate_api_key(raw_key: str) -> Optional[APIKey]:
    """Validate an API key and return the key data."""
    storage = get_storage()
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    api_key = storage.get_api_key_by_hash(key_hash)

    if not api_key:
        return None
    if not api_key.is_active:
        return None
    if api_key.expires_at and datetime.now() > datetime.fromisoformat(str(api_key.expires_at)):
        return None

    # Update last used
    storage.update_api_key_last_used(api_key.key_id)
    return api_key


# ============================================================================
# FastAPI Dependencies
# ============================================================================


class AuthResult(BaseModel):
    """Result of authentication."""

    authenticated: bool = False
    auth_type: Optional[str] = None  # "jwt", "api_key", or None
    user_id: Optional[str] = None
    username: Optional[str] = None
    scopes: list[str] = []


async def get_current_auth(
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    api_key: Optional[str] = Depends(api_key_header),
) -> AuthResult:
    """
    Get current authentication from either JWT or API key.
    Returns AuthResult with authentication details.
    Does not raise - returns unauthenticated result if no valid auth.
    """
    # Try JWT Bearer token first
    if bearer and bearer.credentials:
        try:
            token_data = decode_token(bearer.credentials)
            return AuthResult(
                authenticated=True,
                auth_type="jwt",
                user_id=token_data.sub,
                username=token_data.username,
                scopes=token_data.scopes,
            )
        except HTTPException:
            pass  # Invalid token, try API key

    # Try API key
    if api_key:
        key_data = validate_api_key(api_key)
        if key_data:
            return AuthResult(
                authenticated=True,
                auth_type="api_key",
                user_id=key_data.key_id,
                username=key_data.name,
                scopes=key_data.scopes,
            )

    # No valid authentication
    return AuthResult(authenticated=False)


async def require_auth(
    auth: AuthResult = Depends(get_current_auth),
) -> AuthResult:
    """Require authentication - raises 401 if not authenticated."""
    if not auth.authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth


def require_scopes(*required_scopes: str):
    """
    Create a dependency that requires specific scopes.

    Usage:
        @app.get("/admin", dependencies=[Depends(require_scopes("admin"))])
        async def admin_endpoint():
            ...
    """

    async def scope_checker(auth: AuthResult = Depends(require_auth)) -> AuthResult:
        for scope in required_scopes:
            if scope not in auth.scopes and "admin" not in auth.scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required scope: {scope}",
                )
        return auth

    return scope_checker
