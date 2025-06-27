"""
JWT Authentication for multi-platform parsing service.
"""

import logging
from typing import Optional
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import httpx
import os

from .config import settings

logger = logging.getLogger(__name__)

security = HTTPBearer()

API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://api-gateway:8000")


class AuthenticationError(HTTPException):
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=401,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_user_id_by_email_via_api_gateway(email: str) -> Optional[int]:
    """Получить user_id по email через API Gateway (как в integration-service)"""
    logger.info(f"🔍 Parsing Service: запрос user_id для email: '{email}'")
    url = f"{API_GATEWAY_URL}/internal/users/by-email?email={email}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return data["id"]
            elif resp.status_code == 404:
                return None
            else:
                logger.error(f"API Gateway error: {resp.status_code} {resp.text}")
                raise AuthenticationError("User service unavailable")
    except Exception as e:
        logger.error(f"Error getting user by email: {e}")
        raise AuthenticationError("User service unavailable")


def decode_jwt_token(token: str) -> Optional[dict]:
    """
    Decode JWT token and extract user information.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.error("JWT token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid JWT token: {e}")
        return None


def get_user_id_from_token(token: str) -> Optional[int]:
    """
    Extract user_id from JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        User ID or None if token is invalid
    """
    payload = decode_jwt_token(token)
    if payload:
        return payload.get("user_id") or payload.get("sub")
    return None


async def get_user_id_from_request(request: Request) -> int:
    """
    Extract user_id from request JWT token.
    Converts email to user_id via API Gateway if needed.
    
    Args:
        request: FastAPI request object
        
    Returns:
        User ID (integer)
        
    Raises:
        AuthenticationError: If token is missing or invalid
    """
    # Get token from Authorization header
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth_header:
        logger.error("🚫 Missing Authorization header")
        raise AuthenticationError("Authorization header missing")
    
    # Extract token from "Bearer <token>"
    if not auth_header.startswith("Bearer "):
        logger.error("🚫 Invalid Authorization header format")
        raise AuthenticationError("Invalid Authorization header format")
    
    token = auth_header[7:]
    logger.info(f"🔍 Processing JWT token: {token[:30]}...")
    
    try:
        # Decode JWT token
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        email = payload.get("sub")
        if not email:
            logger.error(f"🚫 JWT token missing 'sub' field: {payload}")
            raise AuthenticationError("Invalid token: missing email")
        
        logger.info(f"🔍 JWT PAYLOAD: {payload}")
        logger.info(f"🔍 USER EMAIL: '{email}'")
        
        # Преобразуем email в user_id через API Gateway (как в integration-service)
        if "@" in email:
            user_id = await get_user_id_by_email_via_api_gateway(email)
            if not user_id:
                logger.error(f"🚫 User not found for email: {email}")
                raise AuthenticationError("Invalid token: user not found")
            
            logger.info(f"✅ JWT Authentication successful - User ID: {user_id}")
            return user_id
        else:
            # Если в токене уже user_id
            user_id = int(email)
            logger.info(f"✅ JWT Authentication successful - User ID: {user_id}")
            return user_id
            
    except jwt.ExpiredSignatureError:
        logger.error("🚫 JWT token expired")
        raise AuthenticationError("Token expired")
    except jwt.InvalidTokenError as e:
        logger.error(f"🚫 Invalid JWT token: {e}")
        raise AuthenticationError("Invalid token")
    except Exception as e:
        logger.error(f"🚫 Authentication error: {e}")
        raise AuthenticationError("Authentication failed")


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> int:
    """
    FastAPI dependency to get current user ID from JWT token.
    
    Args:
        credentials: HTTP Authorization credentials
        
    Returns:
        User ID
        
    Raises:
        HTTPException: If token is invalid
    """
    user_id = get_user_id_from_token(credentials.credentials)
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )
    return user_id


def require_auth(func):
    """
    Decorator to require authentication for endpoints.
    
    Usage:
        @require_auth
        async def my_endpoint(user_id: int = Depends(get_current_user_id)):
            pass
    """
    return func 