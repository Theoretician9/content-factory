from fastapi import HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from typing import Optional
import logging
from .config import get_settings

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)  # Не auto_error, проверяем вручную

# Константа JWT секрета (синхронизировано с docker-compose)
JWT_SECRET = "super-secret-jwt-key-for-content-factory-2024"

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
    
    # Принудительная проверка наличия токена
    if not credentials:
        logger.error("🚫 Missing Authorization header")
        raise AuthenticationError("Authorization header missing")
    
    try:
        # Получаем токен из заголовка Authorization
        token = credentials.credentials
        logger.info(f"🔍 Processing JWT token: {token[:30]}...")
        
        # Используем правильный JWT секрет
        jwt_secret = "super-secret-jwt-key-for-content-factory-2024"
        
        # Декодируем JWT токен
        payload = jwt.decode(
            token, 
            jwt_secret, 
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
        
        logger.info(f"🔐 JWT Authentication successful - User ID: {user_id_int}, Token payload: {payload}")
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

async def get_user_id_from_request(request: Request) -> int:
    """
    Функция авторизации - сначала проверяет middleware state, 
    затем читает токен напрямую из заголовков (fallback).
    """
    # ПРИОРИТЕТ 1: Проверяем результат middleware
    if hasattr(request.state, 'user_id') and request.state.user_id:
        user_id = request.state.user_id
        logger.error(f"✅ Using user_id from middleware state: {user_id}")
        return user_id
    
    # ПРИОРИТЕТ 2: Парсим JWT напрямую (fallback)
    logger.error("🔄 Middleware state not found, parsing JWT directly...")
    
    # Получаем Authorization header напрямую
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    
    if not auth_header:
        logger.error("🚫 Missing Authorization header in request")
        raise AuthenticationError("Authorization header missing")
    
    # Проверяем формат Bearer token
    if not auth_header.startswith("Bearer "):
        logger.error("🚫 Invalid Authorization header format")
        raise AuthenticationError("Invalid Authorization header format")
    
    # Извлекаем токен
    token = auth_header[7:]  # Убираем "Bearer "
    logger.error(f"🔍 Processing JWT token from request: {token[:30]}...")
    
    try:
        # Попробуем несколько JWT секретов для совместимости
        jwt_secrets = [
            JWT_SECRET,  # Integration Service секрет
            "your-jwt-secret",  # API Gateway секрет
            "super-secret-jwt-key-for-content-factory-2024",  # Fallback
        ]
        
        payload = None
        used_secret = None
        
        for secret in jwt_secrets:
            try:
                payload = jwt.decode(token, secret, algorithms=["HS256"])
                used_secret = secret
                break
            except jwt.InvalidTokenError:
                continue
        
        if not payload:
            logger.error(f"🚫 JWT token failed verification with all secrets")
            raise AuthenticationError("Invalid token: signature verification failed")
        
        # Извлекаем user_id
        user_id_str = payload.get("sub")
        if not user_id_str:
            logger.error(f"🚫 JWT token missing 'sub' field: {payload}")
            raise AuthenticationError("Invalid token: missing user ID")
        
        user_id = int(user_id_str)
        logger.error(f"✅ JWT Authentication successful - User ID: {user_id}, secret: {used_secret[:20]}...")
        return user_id
        
    except jwt.ExpiredSignatureError:
        logger.error("🚫 JWT token expired")
        raise AuthenticationError("Token expired")
    except jwt.InvalidTokenError as e:
        logger.error(f"🚫 Invalid JWT token: {e}")
        raise AuthenticationError("Invalid token")
    except ValueError:
        logger.error("🚫 Invalid user_id format in JWT")
        raise AuthenticationError("Invalid token: invalid user ID format")
    except Exception as e:
        logger.error(f"🚫 Authentication error: {e}")
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