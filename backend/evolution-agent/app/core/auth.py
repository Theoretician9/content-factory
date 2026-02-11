import logging
import os
from typing import Optional

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings


logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)

API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://api-gateway:8000")


class AuthenticationError(HTTPException):
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


async def _get_user_id_by_email_via_api_gateway(email: str) -> Optional[int]:
    """Получить user_id по email через API Gateway (единый паттерн для проекта)."""
    logger.info(f"🔍 evolution-agent: запрос user_id по email '{email}' через API Gateway")
    url = f"{API_GATEWAY_URL}/internal/users/by-email?email={email}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data["id"]
        if resp.status_code == 404:
            return None
        logger.error(f"evolution-agent: API Gateway error {resp.status_code} {resp.text}")
        raise AuthenticationError("User service unavailable")


async def get_user_id_from_request(request: Request) -> int:
    """
    Извлечение user_id из JWT токена в заголовке Authorization.

    Поддерживает:
    - стандартные пользовательские токены (sub=email);
    - сервисные токены (payload['service'], user_id → X-User-Id).
    """
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth_header:
        logger.error("🚫 evolution-agent: missing Authorization header")
        raise AuthenticationError("Authorization header missing")

    if not auth_header.startswith("Bearer "):
        logger.error(f"🚫 evolution-agent: invalid Authorization header format: {auth_header!r}")
        raise AuthenticationError("Invalid Authorization header format")

    token = auth_header[7:]
    settings = get_settings()

    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        logger.info(f"🔍 evolution-agent: JWT PAYLOAD: {payload}")

        # Сервисный токен (межсервисные вызовы)
        service_name = payload.get("service")
        if service_name:
            x_user_id = request.headers.get("X-User-Id") or request.headers.get("x-user-id")
            if not x_user_id:
                logger.error(
                    f"🚫 evolution-agent: service token без X-User-Id "
                    f"(service={service_name}, payload={payload})"
                )
                raise AuthenticationError("Missing X-User-Id for service token")
            try:
                user_id = int(x_user_id)
            except ValueError:
                logger.error(f"🚫 evolution-agent: invalid X-User-Id format: {x_user_id!r}")
                raise AuthenticationError("Invalid X-User-Id format")

            logger.info(
                f"✅ evolution-agent: service JWT ok — service='{service_name}', user_id={user_id}"
            )
            return user_id

        # Пользовательский токен
        sub = payload.get("sub")
        if not sub:
            logger.error(f"🚫 evolution-agent: JWT без 'sub': {payload}")
            raise AuthenticationError("Invalid token: missing user identifier")

        # Если sub — email
        if "@" in sub:
            user_id_val = await _get_user_id_by_email_via_api_gateway(sub)
            if not user_id_val:
                logger.error(f"🚫 evolution-agent: user not found for email '{sub}'")
                raise AuthenticationError("Invalid token: user not found")
            logger.info(f"✅ evolution-agent: user JWT ok — user_id={user_id_val}")
            return user_id_val

        # Если sub — уже user_id (строка/число)
        try:
            user_id = int(sub)
            logger.info(f"✅ evolution-agent: user JWT ok — user_id={user_id}")
            return user_id
        except ValueError:
            logger.error(f"🚫 evolution-agent: invalid user identifier format in sub={sub!r}")
            raise AuthenticationError("Invalid token: bad user identifier")

    except jwt.ExpiredSignatureError:
        logger.error("🚫 evolution-agent: JWT token expired")
        raise AuthenticationError("Token expired")
    except jwt.InvalidTokenError as e:
        logger.error(f"🚫 evolution-agent: invalid JWT token: {e}")
        raise AuthenticationError("Invalid token")
    except AuthenticationError:
        raise
    except Exception as e:
        logger.error(f"🚫 evolution-agent: authentication error: {e}")
        raise AuthenticationError("Authentication failed")


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> int:
    """
    Dependency‑обёртка для использования в эндпоинтах.
    Пригодится для внутренних служебных маршрутов, где удобнее работать с Depends.
    """
    if not credentials:
        raise AuthenticationError("Authorization header missing")

    # Оборачиваем токен в "искусственный" Request для переиспользования основной логики.
    class _MockRequest:
        def __init__(self, token_str: str):
            self.headers = {"authorization": f"Bearer {token_str}"}

    mock_request = _MockRequest(credentials.credentials)
    return await get_user_id_from_request(mock_request)  # type: ignore[arg-type]

