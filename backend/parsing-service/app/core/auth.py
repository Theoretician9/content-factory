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
import traceback

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
    logger.info("🔍 DIAGNOSTIC: Starting get_user_id_from_request")
    logger.info(f"🔍 DIAGNOSTIC: Request headers: {dict(request.headers)}")
    
    # Get token from Authorization header
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    logger.info(f"🔍 DIAGNOSTIC: Auth header present: {bool(auth_header)}")
    
    if not auth_header:
        logger.error("🚫 DIAGNOSTIC: Missing Authorization header")
        logger.error(f"🚫 DIAGNOSTIC: Available headers: {list(request.headers.keys())}")
        raise AuthenticationError("Authorization header missing")
    
    # Extract token from "Bearer <token>"
    if not auth_header.startswith("Bearer "):
        logger.error(f"🚫 DIAGNOSTIC: Invalid Authorization header format: '{auth_header[:50]}...'")
        raise AuthenticationError("Invalid Authorization header format")
    
    token = auth_header[7:]
    logger.info(f"🔍 DIAGNOSTIC: Extracted token length: {len(token)}")
    logger.info(f"🔍 DIAGNOSTIC: Token preview: {token[:50]}...")
    
    try:
        logger.info("🔍 DIAGNOSTIC: Attempting JWT decode...")
        logger.info(f"🔍 DIAGNOSTIC: JWT_SECRET_KEY present: {bool(settings.JWT_SECRET_KEY)}")
        logger.info(f"🔍 DIAGNOSTIC: JWT_SECRET_KEY length: {len(settings.JWT_SECRET_KEY) if settings.JWT_SECRET_KEY else 0}")
        
        # Decode JWT token
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        logger.info(f"🔍 DIAGNOSTIC: JWT decode successful")
        logger.info(f"🔍 DIAGNOSTIC: JWT PAYLOAD: {payload}")
        
        # Поддержка двух форматов токенов:
        # 1. Стандартные JWT с полем 'sub' (email) - от фронтенда
        # 2. Межсервисные токены с полем 'user_id' (integer) - между сервисами
        email_or_user_id = payload.get("sub") or payload.get("user_id")
        logger.info(f"🔍 DIAGNOSTIC: Extracted email/user_id: '{email_or_user_id}' (type: {type(email_or_user_id)})")
        
        if not email_or_user_id:
            logger.error(f"🚫 DIAGNOSTIC: JWT token missing both 'sub' and 'user_id' fields in payload: {payload}")
            raise AuthenticationError("Invalid token: missing user identifier")
        
        # Если это числовой user_id (межсервисный токен)
        if isinstance(email_or_user_id, int):
            logger.info(f"🔍 DIAGNOSTIC: Inter-service token detected with user_id: {email_or_user_id}")
            logger.info(f"✅ DIAGNOSTIC: JWT Authentication successful - User ID: {email_or_user_id}")
            return email_or_user_id
        
        # Если это email (стандартный JWT токен от фронтенда)
        email = str(email_or_user_id)
        if "@" in email:
            logger.info(f"🔍 DIAGNOSTIC: Standard JWT token detected, calling API Gateway for user_id")
            user_id = await get_user_id_by_email_via_api_gateway(email)
            logger.info(f"🔍 DIAGNOSTIC: API Gateway returned user_id: {user_id}")
            
            if not user_id:
                logger.error(f"🚫 DIAGNOSTIC: User not found for email: {email}")
                raise AuthenticationError("Invalid token: user not found")
            
            logger.info(f"✅ DIAGNOSTIC: JWT Authentication successful - User ID: {user_id}")
            return user_id
        else:
            # Если это строковый user_id
            logger.info(f"🔍 DIAGNOSTIC: String user_id format detected, converting to int")
            try:
                user_id = int(email)
                logger.info(f"✅ DIAGNOSTIC: JWT Authentication successful - User ID: {user_id}")
                return user_id
            except ValueError:
                logger.error(f"🚫 DIAGNOSTIC: Invalid user identifier format: {email}")
                raise AuthenticationError("Invalid token: bad user identifier")
            
    except jwt.ExpiredSignatureError as e:
        logger.error(f"🚫 DIAGNOSTIC: JWT token expired: {e}")
        logger.error(f"🚫 DIAGNOSTIC: JWT expired traceback: {traceback.format_exc()}")
        raise AuthenticationError("Token expired")
    except jwt.InvalidTokenError as e:
        logger.error(f"🚫 DIAGNOSTIC: Invalid JWT token: {e}")
        logger.error(f"🚫 DIAGNOSTIC: JWT invalid traceback: {traceback.format_exc()}")
        raise AuthenticationError("Invalid token")
    except Exception as e:
        logger.error(f"🚫 DIAGNOSTIC: Authentication error: {e}")
        logger.error(f"🚫 DIAGNOSTIC: Authentication traceback: {traceback.format_exc()}")
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