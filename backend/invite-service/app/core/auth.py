"""
JWT аутентификация для Invite Service
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from typing import Optional
import httpx

from .config import settings

# auto_error=False — при отсутствии заголовка возвращаем 401 из get_current_user_id, а не 403 от HTTPBearer
security = HTTPBearer(auto_error=False)


async def _get_user_id_by_email(email: str) -> Optional[int]:
    """Резолв user_id по email через API Gateway (internal/users/by-email)."""
    url = f"{settings.API_GATEWAY_URL}/internal/users/by-email"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, params={"email": email})
            if resp.status_code == 200:
                data = resp.json()
                return data.get("id")
            if resp.status_code == 404:
                return None
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="User service unavailable"
            )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"API Gateway unreachable: {str(e)}"
        )


async def get_current_user_id(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> int:
    """
    Извлечение user_id из JWT токена.
    Если в sub указан email — запрос к API Gateway /internal/users/by-email.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header"
        )
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=["HS256"]
        )
        sub = payload.get("sub")
        if sub is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: no user email"
            )
        # Сервисный токен (service:invite-service) не используется для пользовательских эндпоинтов
        if isinstance(sub, str) and "@" in sub:
            user_id = await _get_user_id_by_email(sub)
            if user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found"
                )
            return user_id
        # sub уже числовой id (строка)
        try:
            return int(sub)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: invalid user id"
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )

async def get_current_user_id_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[int]:
    """
    Опциональное извлечение user_id из JWT токена (для публичных endpoints)
    """
    if not credentials:
        return None
    try:
        return await get_current_user_id(credentials)
    except HTTPException:
        return None 