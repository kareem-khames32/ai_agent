"""
Simple Authentication Storage
Uses SQLite for users and API keys
"""
import json
import uuid
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from .sqlite_db import db


def hash_password(password: str, salt: str = None) -> tuple:
    """Hash password with salt"""
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return salt + ":" + hashed.hex(), salt


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored hash"""
    try:
        salt, hashed = stored_hash.split(":")
        new_hash, _ = hash_password(password, salt)
        return new_hash == stored_hash
    except Exception:
        return False


def generate_api_key() -> tuple:
    """Generate API key with prefix and hash"""
    # Generate 32-byte key
    key = secrets.token_urlsafe(32)
    prefix = "va_" + key[:8]  # va = voice ai
    full_key = f"va_{key}"

    # Hash for storage
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()

    return full_key, prefix, key_hash


def generate_token(user_id: str, expires_hours: int = 24) -> str:
    """Generate simple session token"""
    token_data = {
        "user_id": user_id,
        "exp": (datetime.utcnow() + timedelta(hours=expires_hours)).isoformat(),
        "jti": secrets.token_urlsafe(16)
    }
    # Simple encoding (in production, use JWT)
    import base64
    encoded = base64.urlsafe_b64encode(json.dumps(token_data).encode()).decode()
    return encoded


def decode_token(token: str) -> Optional[Dict]:
    """Decode session token"""
    try:
        import base64
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        data = json.loads(decoded)

        # Check expiration
        exp = datetime.fromisoformat(data["exp"])
        if datetime.utcnow() > exp:
            return None

        return data
    except Exception:
        return None


class AuthStore:
    """Authentication storage using SQLite"""

    def create_user(self, email: str, password: str, name: str = None) -> Optional[Dict]:
        """Create a new user"""
        # Check if exists
        existing = db.fetch_one("SELECT id FROM users WHERE email = ?", (email.lower(),))
        if existing:
            return None

        user_id = str(uuid.uuid4())
        password_hash, _ = hash_password(password)
        now = datetime.utcnow().isoformat()

        db.execute("""
            INSERT INTO users (id, email, password_hash, name, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?)
        """, (user_id, email.lower(), password_hash, name or email.split("@")[0], now, now))

        return self.get_user(user_id)

    def get_user(self, user_id: str) -> Optional[Dict]:
        """Get user by ID"""
        row = db.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
        if row:
            return {
                "id": row["id"],
                "email": row["email"],
                "name": row["name"],
                "is_active": bool(row["is_active"]),
                "created_at": row["created_at"],
            }
        return None

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email with password hash"""
        row = db.fetch_one("SELECT * FROM users WHERE email = ?", (email.lower(),))
        if row:
            return {
                "id": row["id"],
                "email": row["email"],
                "name": row["name"],
                "is_active": bool(row["is_active"]),
                "password_hash": row["password_hash"],
                "created_at": row["created_at"],
            }
        return None

    def authenticate(self, email: str, password: str) -> Optional[str]:
        """
        Authenticate user and return session token

        Returns:
            Session token if successful, None otherwise
        """
        user = self.get_user_by_email(email)
        if not user:
            return None

        if not user["is_active"]:
            return None

        if not verify_password(password, user["password_hash"]):
            return None

        return generate_token(user["id"])

    def validate_token(self, token: str) -> Optional[Dict]:
        """
        Validate session token and return user

        Returns:
            User dict if valid, None otherwise
        """
        data = decode_token(token)
        if not data:
            return None

        return self.get_user(data["user_id"])

    # API Keys
    def create_api_key(self, name: str) -> Dict:
        """Create a new API key"""
        key_id = str(uuid.uuid4())
        full_key, prefix, key_hash = generate_api_key()
        now = datetime.utcnow().isoformat()

        db.execute("""
            INSERT INTO api_keys (id, name, key_hash, prefix, is_active, created_at)
            VALUES (?, ?, ?, ?, 1, ?)
        """, (key_id, name, key_hash, prefix, now))

        return {
            "id": key_id,
            "name": name,
            "key": full_key,  # Only returned once!
            "prefix": prefix,
            "created_at": now,
        }

    def validate_api_key(self, api_key: str) -> bool:
        """Validate an API key"""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        row = db.fetch_one(
            "SELECT * FROM api_keys WHERE key_hash = ? AND is_active = 1",
            (key_hash,)
        )

        if row:
            # Update last used
            db.execute(
                "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), row["id"])
            )
            return True

        return False

    def list_api_keys(self) -> List[Dict]:
        """List all API keys (without the actual key)"""
        rows = db.fetch_all("SELECT * FROM api_keys ORDER BY created_at DESC")
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "prefix": row["prefix"],
                "is_active": bool(row["is_active"]),
                "last_used_at": row["last_used_at"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def delete_api_key(self, key_id: str) -> bool:
        """Delete an API key"""
        existing = db.fetch_one("SELECT id FROM api_keys WHERE id = ?", (key_id,))
        if not existing:
            return False

        db.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
        return True


# Global instance
auth_store = AuthStore()
