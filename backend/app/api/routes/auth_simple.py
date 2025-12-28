"""
Simple Authentication API Routes
Uses SQLite storage - no PostgreSQL needed
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, EmailStr

from app.storage.auth_store import auth_store

router = APIRouter()


# === Request/Response Models ===

class RegisterRequest(BaseModel):
    """User registration request"""
    email: EmailStr
    password: str
    name: Optional[str] = None


class LoginRequest(BaseModel):
    """User login request"""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Authentication token response"""
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    """User profile response"""
    id: str
    email: str
    name: str
    is_active: bool


class ApiKeyCreate(BaseModel):
    """API key creation request"""
    name: str


class ApiKeyResponse(BaseModel):
    """API key response"""
    id: str
    name: str
    key: Optional[str] = None  # Only returned on creation
    prefix: str
    created_at: str


# === Authentication Dependency ===

async def get_current_user(authorization: Optional[str] = Header(None)):
    """
    Get current user from Authorization header

    Supports both:
    - Bearer token: Authorization: Bearer <token>
    - API key: Authorization: Bearer va_<key>
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Extract token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = parts[1]

    # Check if it's an API key
    if token.startswith("va_"):
        if auth_store.validate_api_key(token):
            # API key is valid - return system user
            return {"id": "api", "email": "api@system", "name": "API User", "is_active": True}
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Validate session token
    user = auth_store.validate_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return user


# Optional auth - doesn't require authentication but uses it if provided
async def get_optional_user(authorization: Optional[str] = Header(None)):
    """Get current user if authenticated, None otherwise"""
    if not authorization:
        return None

    try:
        return await get_current_user(authorization)
    except HTTPException:
        return None


# === API Endpoints ===

@router.post("/register", response_model=TokenResponse)
async def register(data: RegisterRequest):
    """
    Register a new user

    Creates a new user account and returns an access token.
    """
    user = auth_store.create_user(
        email=data.email,
        password=data.password,
        name=data.name
    )

    if not user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Auto-login after registration
    token = auth_store.authenticate(data.email, data.password)

    return TokenResponse(
        access_token=token,
        user=user
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest):
    """
    Login with email and password

    Returns an access token for API authentication.
    """
    token = auth_store.authenticate(data.email, data.password)

    if not token:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user = auth_store.get_user_by_email(data.email)
    user_response = {k: v for k, v in user.items() if k != "password_hash"}

    return TokenResponse(
        access_token=token,
        user=user_response
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    """
    Get current user profile

    Requires authentication via Bearer token.
    """
    return UserResponse(**user)


@router.post("/api-keys", response_model=ApiKeyResponse)
async def create_api_key(data: ApiKeyCreate, user: dict = Depends(get_current_user)):
    """
    Create a new API key

    The full API key is only returned once during creation.
    Store it securely - it cannot be retrieved later.
    """
    api_key = auth_store.create_api_key(data.name)

    return ApiKeyResponse(
        id=api_key["id"],
        name=api_key["name"],
        key=api_key["key"],  # Only returned on creation!
        prefix=api_key["prefix"],
        created_at=api_key["created_at"]
    )


@router.get("/api-keys")
async def list_api_keys(user: dict = Depends(get_current_user)):
    """
    List all API keys

    Returns API keys without the actual key values.
    """
    return auth_store.list_api_keys()


@router.delete("/api-keys/{key_id}")
async def delete_api_key(key_id: str, user: dict = Depends(get_current_user)):
    """
    Delete an API key

    This action cannot be undone.
    """
    if not auth_store.delete_api_key(key_id):
        raise HTTPException(status_code=404, detail="API key not found")

    return {"message": "API key deleted"}


# === Health Check (no auth required) ===

@router.get("/health")
async def auth_health():
    """Check authentication service health"""
    return {"status": "healthy", "service": "auth"}
