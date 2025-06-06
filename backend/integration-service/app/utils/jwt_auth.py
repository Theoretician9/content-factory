from fastapi import HTTPException, Request, status
import jwt
import logging

logger = logging.getLogger(__name__)

# JWT секреты для совместимости с основной системой
JWT_SECRETS = [
    "your-jwt-secret",  # API Gateway / основная система
    "super-secret-jwt-key-for-content-factory-2024",  # Integration Service
]

class AuthenticationError(HTTPException):
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

def extract_user_id_from_request(request: Request) -> int:
    """
    Извлекает user_id из JWT токена в заголовке Authorization.
    Обеспечивает изоляцию пользователей во всех endpoints.
    Поддерживает множественные JWT секреты для совместимости.
    """
    # Получаем Authorization header
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    
    if not auth_header:
        logger.error("🚫 Missing Authorization header")
        raise AuthenticationError("Authorization header missing")
    
    # Проверяем формат Bearer token
    if not auth_header.startswith("Bearer "):
        logger.error(f"🚫 Invalid Authorization header format: {auth_header[:20]}...")
        raise AuthenticationError("Invalid Authorization header format")
    
    # Извлекаем токен
    token = auth_header[7:]  # Убираем "Bearer "
    logger.info(f"🔍 Processing JWT token: {token[:30]}...")
    
    try:
        # Попробуем несколько JWT секретов для совместимости с основной системой
        payload = None
        used_secret = None
        last_error = None
        
        for secret in JWT_SECRETS:
            try:
                payload = jwt.decode(token, secret, algorithms=["HS256"])
                used_secret = secret
                logger.info(f"✅ JWT decoded successfully with secret: {secret[:15]}...")
                break
            except jwt.ExpiredSignatureError as e:
                logger.warning(f"🚫 JWT token expired with secret {secret[:15]}...")
                last_error = e
                continue
            except jwt.InvalidTokenError as e:
                logger.warning(f"🚫 JWT invalid with secret {secret[:15]}...: {e}")
                last_error = e
                continue
        
        if not payload:
            logger.error(f"🚫 JWT token failed verification with all secrets")
            if isinstance(last_error, jwt.ExpiredSignatureError):
                raise AuthenticationError("Token expired")
            else:
                raise AuthenticationError("Invalid token: signature verification failed")
        
        # Извлекаем user_id из поля 'sub'
        user_id_str = payload.get("sub")
        if not user_id_str:
            logger.warning(f"🚫 JWT token missing 'sub' field: {payload}")
            raise AuthenticationError("Invalid token: missing user ID")
        
        # Конвертируем в int
        user_id = int(user_id_str)
        logger.info(f"✅ JWT Authentication successful - User ID: {user_id}, Secret: {used_secret[:15]}...")
        return user_id
        
    except AuthenticationError:
        raise
    except ValueError:
        logger.warning("🚫 Invalid user_id format in JWT")
        raise AuthenticationError("Invalid token: invalid user ID format")
    except Exception as e:
        logger.error(f"🚫 Authentication error: {e}")
        raise AuthenticationError("Authentication failed") 