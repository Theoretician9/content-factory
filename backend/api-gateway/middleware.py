from fastapi import Request, HTTPException
from itsdangerous import URLSafeTimedSerializer
from redis import Redis
import os
from datetime import datetime, timedelta
import jwt
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# CSRF middleware
class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, secret_key: str):
        super().__init__(app)
        self.serializer = URLSafeTimedSerializer(secret_key)
        
    async def dispatch(self, request: Request, call_next):
        # Пропускаем CSRF проверку для GET запросов
        if request.method == "GET":
            return await call_next(request)
            
        # Получаем CSRF токен из заголовка
        csrf_token = request.headers.get("X-CSRF-Token")
        if not csrf_token:
            raise HTTPException(status_code=403, detail="CSRF token missing")
            
        try:
            # Проверяем CSRF токен
            self.serializer.loads(csrf_token, max_age=3600)  # токен действителен 1 час
        except:
            raise HTTPException(status_code=403, detail="Invalid CSRF token")
            
        return await call_next(request)

# Refresh token middleware
class RefreshTokenMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_client: Redis, jwt_secret: str):
        super().__init__(app)
        self.redis = redis_client
        self.jwt_secret = jwt_secret
        
    async def dispatch(self, request: Request, call_next):
        # Проверяем наличие refresh token в cookie
        refresh_token = request.cookies.get("refresh_token")
        if not refresh_token:
            return await call_next(request)
            
        try:
            # Проверяем refresh token в Redis
            user_id = self.redis.get(f"refresh_token:{refresh_token}")
            if not user_id:
                return await call_next(request)
                
            # Проверяем JWT токен
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return await call_next(request)
                
            token = auth_header.split(" ")[1]
            try:
                jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            except jwt.ExpiredSignatureError:
                # Если JWT истек, генерируем новый
                new_token = jwt.encode(
                    {
                        "sub": user_id,
                        "exp": datetime.utcnow() + timedelta(minutes=15)
                    },
                    self.jwt_secret,
                    algorithm="HS256"
                )
                response = await call_next(request)
                response.headers["X-New-Token"] = new_token
                return response
                
        except Exception as e:
            print(f"Error in refresh token middleware: {e}")
            
        return await call_next(request) 