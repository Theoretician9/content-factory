#!/usr/bin/env python3
"""
Централизованный сервис авторизации для всех микросервисов.
Обеспечивает изоляцию данных между пользователями.
"""

import jwt
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class SharedAuthService:
    """
    Централизованный сервис авторизации.
    Используется всеми микросервисами для проверки прав доступа.
    """
    
    def __init__(self, jwt_secret: str = "super-secret-jwt-key-for-content-factory-2024"):
        self.jwt_secret = jwt_secret
        self.algorithm = "HS256"
    
    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Проверяет JWT токен и возвращает payload.
        """
        try:
            if not token:
                logger.warning("🚫 Empty token provided")
                return None
            
            # Убираем 'Bearer ' если есть
            if token.startswith('Bearer '):
                token = token[7:]
            
            # Декодируем токен
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.algorithm])
            
            # Проверяем обязательные поля
            user_id = payload.get('sub')
            exp = payload.get('exp')
            
            if not user_id:
                logger.warning("🚫 Token missing user ID")
                return None
            
            if exp and exp < datetime.utcnow().timestamp():
                logger.warning("🚫 Token expired")
                return None
            
            logger.info(f"✅ Token validated for user_id: {user_id}")
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("🚫 Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"🚫 Invalid token: {e}")
            return None
        except Exception as e:
            logger.error(f"🚫 Token validation error: {e}")
            return None
    
    def get_user_id_from_token(self, token: str) -> Optional[int]:
        """
        Извлекает user_id из JWT токена.
        """
        payload = self.validate_token(token)
        if not payload:
            return None
        
        try:
            user_id = int(payload.get('sub'))
            return user_id
        except (ValueError, TypeError):
            logger.warning("🚫 Invalid user_id format in token")
            return None
    
    def create_user_filter(self, user_id: int) -> Dict[str, Any]:
        """
        Создает фильтр для изоляции данных пользователя.
        Используется во всех SQL запросах.
        """
        return {"user_id": user_id}
    
    def check_user_access(self, token: str, resource_user_id: int) -> bool:
        """
        Проверяет имеет ли пользователь доступ к ресурсу.
        """
        token_user_id = self.get_user_id_from_token(token)
        if not token_user_id:
            return False
        
        access_granted = token_user_id == resource_user_id
        logger.info(f"🔒 Access check: token_user={token_user_id}, resource_user={resource_user_id}, granted={access_granted}")
        return access_granted

# Глобальный экземпляр для использования во всех сервисах
auth_service = SharedAuthService()

def get_auth_service() -> SharedAuthService:
    """Возвращает экземпляр сервиса авторизации"""
    return auth_service

# Функции-помощники для интеграции с FastAPI
def extract_user_id_from_request_headers(headers: Dict[str, str]) -> Optional[int]:
    """
    Извлекает user_id из заголовков запроса.
    Используется в микросервисах для получения текущего пользователя.
    """
    auth_header = headers.get('authorization') or headers.get('Authorization')
    if not auth_header:
        logger.warning("🚫 No Authorization header found")
        return None
    
    return auth_service.get_user_id_from_token(auth_header)

def ensure_user_isolation_in_query(user_id: int, base_filters: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Добавляет фильтр пользователя к существующим фильтрам запроса.
    Обеспечивает изоляцию данных на уровне БД.
    """
    filters = base_filters or {}
    filters.update(auth_service.create_user_filter(user_id))
    return filters

# Инструкции по интеграции для других микросервисов:
"""
1. PARSING SERVICE - добавить проверку user_id для всех Telegram аккаунтов
2. MAILING SERVICE - фильтровать аккаунты по user_id 
3. BILLING SERVICE - привязать тарифы к user_id
4. CONTENT SERVICE - изолировать контент по пользователям
5. FUNNEL SERVICE - воронки только для конкретного пользователя

Пример использования в любом микросервисе:

```python
from shared_auth_service import extract_user_id_from_request_headers, ensure_user_isolation_in_query

@app.get("/api/my-resource")
async def get_user_resources(request: Request):
    # Получаем user_id из токена
    user_id = extract_user_id_from_request_headers(dict(request.headers))
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Применяем фильтр пользователя к запросу
    filters = ensure_user_isolation_in_query(user_id, {"active": True})
    
    # Выполняем запрос с изоляцией
    resources = await db.query(MyResource).filter_by(**filters).all()
    return resources
```
""" 