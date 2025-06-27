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
    
    Args:
        request: FastAPI request object
        
    Returns:
        User ID
        
    Raises:
        HTTPException: If token is missing or invalid
    """
    # Get token from Authorization header
    auth_header = request.headers.get("authorization")
    if not auth_header:
        raise HTTPException(
            status_code=401,
            detail="Authorization header missing"
        )
    
    # Extract token from "Bearer <token>"
    try:
        scheme, token = auth_header.split(" ", 1)
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=401,
                detail="Invalid authorization scheme"
            )
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format"
        )
    
    # Decode token and get user_id
    user_id = get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )
    
    return user_id


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