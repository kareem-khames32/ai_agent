"""
Security utilities for authentication and encryption
"""
import secrets
from datetime import datetime, timedelta
from typing import Optional, Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from cryptography.fernet import Fernet
import base64
import hashlib

from app.core.config import settings


# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT token"""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key and its hash

    Returns:
        tuple: (plain_key, hashed_key)
    """
    # Generate a random key with prefix
    random_part = secrets.token_urlsafe(32)
    plain_key = f"vapi_{random_part}"

    # Hash the key for storage
    hashed_key = hashlib.sha256(plain_key.encode()).hexdigest()

    return plain_key, hashed_key


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """Verify an API key against its hash"""
    computed_hash = hashlib.sha256(plain_key.encode()).hexdigest()
    return secrets.compare_digest(computed_hash, hashed_key)


def get_key_prefix(plain_key: str) -> str:
    """Get the prefix of an API key for display"""
    if len(plain_key) > 12:
        return f"{plain_key[:8]}...{plain_key[-4:]}"
    return plain_key


# Encryption for storing sensitive data (API keys, credentials)
def _get_fernet() -> Fernet:
    """Get Fernet instance for encryption"""
    # Ensure key is 32 bytes
    key = settings.ENCRYPTION_KEY.encode()
    key = hashlib.sha256(key).digest()
    key = base64.urlsafe_b64encode(key)
    return Fernet(key)


def encrypt_value(value: str) -> str:
    """Encrypt a value"""
    fernet = _get_fernet()
    encrypted = fernet.encrypt(value.encode())
    return encrypted.decode()


def decrypt_value(encrypted_value: str) -> str:
    """Decrypt a value"""
    fernet = _get_fernet()
    decrypted = fernet.decrypt(encrypted_value.encode())
    return decrypted.decode()
