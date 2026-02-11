from fastapi import HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from typing import Optional
import logging
from .config import get_settings
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.vault import IntegrationVaultClient
from app.database import get_async_session
from app.models.user import User
import os
import httpx

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)  # Не auto_error, проверяем вручную

# Создаем экземпляр Vault клиента
vault_client = IntegrationVaultClient()

API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://api-gateway:8000")

class AuthenticationError(HTTPException):
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_user_id_by_email_via_api_gateway(email: str) -> int:
    # Логируем email перед отправкой запроса
    logger.info(f"🔍 Integration Service: отправка запроса на поиск пользователя по email: '{email}'")
    url = f"{API_GATEWAY_URL}/internal/users/by-email?email={email}"
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

async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> int:
    """
    Извлекает user_id из JWT токена.
    Используется во всех защищенных endpoints.
    """
    settings = get_settings()
    if not credentials:
        logger.error("🚫 Missing Authorization header")
        raise AuthenticationError("Authorization header missing")
    try:
        token = credentials.credentials
        logger.info(f"🔍 Processing JWT token: {token[:30]}...")
        jwt_secret = settings.JWT_SECRET_KEY
        payload = jwt.decode(token, jwt_secret, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            logger.warning(f"JWT token missing 'sub' field: {payload}")
            raise AuthenticationError("Invalid token: missing user ID")
        if "@" in user_id:
            user_id_val = await get_user_id_by_email_via_api_gateway(user_id)
            if not user_id_val:
                logger.warning(f"User not found for email: {user_id}")
                raise AuthenticationError("Invalid token: user not found")
            logger.info(f"🔐 JWT Authentication successful - User ID: {user_id_val}, Token payload: {payload}")
            return user_id_val
        else:
            user_id_int = int(user_id)
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
    Функция авторизации - читает токен напрямую из заголовков.
    Обеспечивает изоляцию пользователей между разными user_id.
    """
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth_header:
        logger.error("🚫 Missing Authorization header in request")
        raise AuthenticationError("Authorization header missing")
    if not auth_header.startswith("Bearer "):
        logger.error("🚫 Invalid Authorization header format")
        raise AuthenticationError("Invalid Authorization header format")
    token = auth_header[7:]
    logger.info(f"🔍 Processing JWT token from request: {token[:30]}...")
    settings = get_settings()
    try:
        jwt_secret = settings.JWT_SECRET_KEY
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        logger.info(f"🔍 JWT PAYLOAD DEBUG: {payload}")

        # Поддержка сервисной аутентификации:
        # если токен содержит поле "service", считаем его сервисным
        service_name = payload.get("service")
        if service_name:
            # Для сервисов (invite-service, parsing-service и т.п.) user_id
            # передаётся явно через заголовок X-User-Id.
            x_user_id = (
                request.headers.get("X-User-Id")
                or request.headers.get("x-user-id")
            )
            if not x_user_id:
                logger.error(
                    f"🚫 Service token без X-User-Id: service={service_name}, payload={payload}"
                )
                raise AuthenticationError("Missing X-User-Id for service token")
            try:
                user_id = int(x_user_id)
            except ValueError:
                logger.error(f"🚫 Invalid X-User-Id format: '{x_user_id}'")
                raise AuthenticationError("Invalid X-User-Id format")

            logger.info(
                f"✅ Service JWT Authentication successful - "
                f"service='{service_name}', user_id={user_id}"
            )
            return user_id

        # Обычная пользовательская аутентификация по email / user_id в 'sub'
        user_id_str = payload.get("sub")
        if not user_id_str:
            logger.error(f"🚫 JWT token missing 'sub' field: {payload}")
            raise AuthenticationError("Invalid token: missing user ID")

        logger.info(f"🔍 USER_ID DEBUG: '{user_id_str}' (type: {type(user_id_str)})")
        if "@" in user_id_str:
            user_id_val = await get_user_id_by_email_via_api_gateway(user_id_str)
            if not user_id_val:
                logger.error(f"🚫 User not found for email: {user_id_str}")
                raise AuthenticationError("Invalid token: user not found")
            logger.info(f"✅ JWT Authentication successful - User ID: {user_id_val}")
            return user_id_val
        else:
            user_id = int(user_id_str)
            logger.info(f"✅ JWT Authentication successful - User ID: {user_id}")
            return user_id
    except jwt.ExpiredSignatureError:
        logger.error("🚫 JWT token expired")
        raise AuthenticationError("Token expired")
    except jwt.InvalidTokenError as e:
        logger.error(f"🚫 Invalid JWT token: {e}")
        raise AuthenticationError("Invalid token: signature verification failed")
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

async def get_user_by_email(email: str, db: AsyncSession) -> Optional[User]:
    """Получить пользователя по email из базы данных"""
    try:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            logger.info(f"✅ User found by email: {email}")
        else:
            logger.warning(f"⚠️ User not found by email: {email}")
        return user
    except Exception as e:
        logger.error(f"🚫 Error getting user by email: {e}")
        return None

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_async_session)
) -> int:
    """
    Получает текущего пользователя из JWT токена
    Возвращает user_id
    """
    try:
        # Получаем JWT секрет из Vault
        jwt_secret = vault_client.get_secret("jwt_secret")
        if not jwt_secret:
            logger.error("🚫 JWT secret not found in Vault")
            raise AuthenticationError("JWT secret not configured")

        # Получаем токен из заголовка
        token = credentials.credentials
        logger.info(f"🔍 Processing JWT token from request: {token[:20]}...")

        # Валидируем токен
        try:
            payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
            logger.info(f"🔍 JWT PAYLOAD DEBUG: {payload}")
        except JWTError as e:
            logger.error(f"🚫 JWT decode error: {e}")
            raise AuthenticationError("Invalid token")

        # Извлекаем email из токена
        email = payload.get("sub")
        if not email:
            logger.error(f"🚫 JWT token missing 'sub' field: {payload}")
            raise AuthenticationError("Invalid token: missing email")

        logger.info(f"🔍 USER_EMAIL DEBUG: '{email}' (type: {type(email)})")

        # Получаем пользователя из базы по email
        user = await get_user_by_email(email, db)
        if not user:
            logger.error(f"🚫 User not found for email: {email}")
            raise AuthenticationError("Invalid token: user not found")

        logger.info(f"✅ JWT Authentication successful - User ID: {user.id}")
        return user.id

    except AuthenticationError as e:
        logger.error(f"🚫 Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"🚫 Unexpected error in get_current_user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) 