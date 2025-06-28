"""
JWT аутентификация для Invite Service
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from typing import Optional

from .config import get_settings

settings = get_settings()
security = HTTPBearer()

def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    """
    Извлечение user_id из JWT токена
    """
    try:
        # Извлекаем токен из заголовка Authorization
        token = credentials.credentials
        
        # Декодируем JWT токен
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=["HS256"]
        )
        
        # Извлекаем email из payload
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: no user email"
            )
        
        # TODO: Здесь должна быть логика извлечения user_id по email
        # Пока возвращаем заглушку
        # В реальной реализации нужно:
        # 1. Обратиться к User Service через HTTP API
        # 2. Получить user_id по email
        # 3. Кэшировать результат
        
        return 1  # Заглушка - возвращаем user_id = 1
        
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )

def get_current_user_id_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[int]:
    """
    Опциональное извлечение user_id из JWT токена (для публичных endpoints)
    """
    if not credentials:
        return None
    
    try:
        return get_current_user_id(credentials)
    except HTTPException:
        return None 