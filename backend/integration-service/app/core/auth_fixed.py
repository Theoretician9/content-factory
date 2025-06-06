from fastapi import HTTPException, Request, status
import jwt
import logging

logger = logging.getLogger(__name__)

# JWT секрет (синхронизировано с docker-compose)
JWT_SECRET = "your-jwt-secret"

class AuthenticationError(HTTPException):
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_user_id_from_request(request: Request) -> int:
    """
    Надежная функция авторизации - читает токен напрямую из заголовков.
    Работает через API Gateway proxy.
    """
    # Получаем Authorization header напрямую из запроса
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    
    if not auth_header:
        logger.error("🚫 Missing Authorization header in request")
        raise AuthenticationError("Authorization header missing")
    
    # Проверяем формат Bearer token
    if not auth_header.startswith("Bearer "):
        logger.error(f"🚫 Invalid Authorization header format: {auth_header[:20]}...")
        raise AuthenticationError("Invalid Authorization header format")
    
    # Извлекаем токен
    token = auth_header[7:]  # Убираем "Bearer "
    logger.info(f"🔍 Processing JWT token from request: {token[:30]}...")
    
    try:
        # Декодируем JWT токен с правильным секретом
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        
        # Извлекаем user_id из поля 'sub'
        user_id_str = payload.get("sub")
        if not user_id_str:
            logger.warning(f"🚫 JWT token missing 'sub' field: {payload}")
            raise AuthenticationError("Invalid token: missing user ID")
        
        # Конвертируем в int
        user_id = int(user_id_str)
        logger.info(f"✅ JWT Authentication successful - User ID: {user_id}")
        return user_id
        
    except jwt.ExpiredSignatureError:
        logger.warning("🚫 JWT token expired")
        raise AuthenticationError("Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"🚫 Invalid JWT token: {e}")
        raise AuthenticationError("Invalid token")
    except ValueError:
        logger.warning("🚫 Invalid user_id format in JWT")
        raise AuthenticationError("Invalid token: invalid user ID format")
    except Exception as e:
        logger.error(f"🚫 Authentication error: {e}")
        raise AuthenticationError("Authentication failed")

def get_user_id_sync(request: Request) -> int:
    """
    Синхронная версия получения user_id из запроса.
    """
    import asyncio
    return asyncio.run(get_user_id_from_request(request)) 