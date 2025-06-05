from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from typing import Optional
import logging
from .config import get_settings

logger = logging.getLogger(__name__)
security = HTTPBearer()

class AuthenticationError(HTTPException):
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> int:
    """
    Извлекает user_id из JWT токена.
    Используется во всех защищенных endpoints.
    """
    settings = get_settings()
    
    try:
        # Получаем токен из заголовка Authorization
        token = credentials.credentials
        
        # Декодируем JWT токен
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        # Извлекаем user_id из поля 'sub' (subject)
        user_id: str = payload.get("sub")
        if user_id is None:
            logger.warning(f"JWT token missing 'sub' field: {payload}")
            raise AuthenticationError("Invalid token: missing user ID")
        
        # Конвертируем в int
        try:
            user_id_int = int(user_id)
        except ValueError:
            logger.warning(f"Invalid user_id format in JWT: {user_id}")
            raise AuthenticationError("Invalid token: invalid user ID format")
        
        logger.info(f"Authenticated user: {user_id_int}")
        return user_id_int
        
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        raise AuthenticationError("Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        raise AuthenticationError("Invalid token")
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise AuthenticationError("Authentication failed")

async def get_optional_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[int]:
    """
    Опциональная авторизация - возвращает user_id если токен валидный, иначе None.
    Используется для публичных endpoints с опциональной авторизацией.
    """
    if not credentials:
        return None
    
    try:
        return await get_current_user_id(credentials)
    except AuthenticationError:
        return None 