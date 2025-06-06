from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import jwt
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware для централизованной авторизации.
    Проверяет JWT токены для всех защищенных endpoints.
    """
    
    def __init__(self, app, jwt_secret: str):
        super().__init__(app)
        self.jwt_secret = jwt_secret
        self.protected_paths = [
            "/api/v1/telegram/accounts",
            "/api/v1/telegram/connect", 
            "/api/v1/telegram/qr-code",
            "/api/v1/telegram/qr-check",
            "/api/v1/telegram/logs",
            "/api/v1/telegram/stats",
            "/api/v1/telegram/test-auth"
        ]
        self.public_paths = [
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc"
        ]
    
    async def dispatch(self, request: Request, call_next):
        # Проверяем нужна ли авторизация для этого пути
        path = request.url.path
        
        # Публичные пути - пропускаем
        if any(path.startswith(public_path) for public_path in self.public_paths):
            return await call_next(request)
        
        # Защищенные пути - требуют авторизацию
        if any(path.startswith(protected_path) for protected_path in self.protected_paths):
            user_id = await self._authenticate_request(request)
            if not user_id:
                return JSONResponse(
                    status_code=401, 
                    content={"detail": "Authentication required"}
                )
            
            # Добавляем user_id в состояние запроса
            request.state.user_id = user_id
            logger.info(f"🔐 Authenticated user_id={user_id} for {path}")
        
        return await call_next(request)
    
    async def _authenticate_request(self, request: Request) -> Optional[int]:
        """Извлекает и проверяет JWT токен из запроса"""
        try:
            # Получаем Authorization header
            auth_header = request.headers.get("authorization")
            if not auth_header:
                logger.warning("🚫 Missing Authorization header")
                return None
            
            # Проверяем формат Bearer token
            if not auth_header.startswith("Bearer "):
                logger.warning("🚫 Invalid Authorization header format")
                return None
            
            # Извлекаем токен
            token = auth_header.split(" ")[1]
            logger.info(f"🔍 Processing JWT token: {token[:30]}...")
            
            # Декодируем JWT
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            
            # Извлекаем user_id
            user_id_str = payload.get("sub")
            if not user_id_str:
                logger.warning("🚫 JWT token missing 'sub' field")
                return None
            
            user_id = int(user_id_str)
            logger.info(f"✅ JWT authentication successful - user_id: {user_id}")
            return user_id
            
        except jwt.ExpiredSignatureError:
            logger.warning("🚫 JWT token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"🚫 Invalid JWT token: {e}")
            return None
        except ValueError:
            logger.warning("🚫 Invalid user_id format in JWT")
            return None
        except Exception as e:
            logger.error(f"🚫 Authentication error: {e}")
            return None 