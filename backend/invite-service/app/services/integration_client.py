"""
HTTP клиент для взаимодействия с Integration Service
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import httpx
import os
import jwt
from dataclasses import dataclass

from app.core.vault import get_vault_client

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Конфигурация retry логики"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


class IntegrationServiceClient:
    """HTTP клиент для взаимодействия с Integration Service"""
    
    def __init__(self):
        self.base_url = os.getenv('INTEGRATION_SERVICE_URL', 'http://integration-service:8000')
        self.timeout = httpx.Timeout(30.0)  # 30 секунд таймаут
        self.retry_config = RetryConfig()
        
        # JWT токен для аутентификации между сервисами
        self._jwt_token = None
        self._jwt_expires_at = None
        
        logger.info(f"Инициализирован Integration Service клиент: {self.base_url}")
    
    async def _get_jwt_token(self) -> str:
        """Получение JWT токена для межсервисной аутентификации"""
        
        # Проверяем актуальность текущего токена
        if self._jwt_token and self._jwt_expires_at:
            if datetime.utcnow() < self._jwt_expires_at - timedelta(minutes=5):  # 5 минут буфер
                return self._jwt_token
        
        try:
            # Получение JWT секрета из Vault
            vault_client = get_vault_client()
            secret_data = vault_client.get_secret("jwt")
            
            if not secret_data or 'secret_key' not in secret_data:
                raise Exception("JWT secret not found in Vault")
            
            jwt_secret = secret_data['secret_key']
            
            # Создание JWT токена для межсервисной аутентификации
            # Integration Service ожидает 'sub' с email пользователя
            payload = {
                'sub': 'nikita.f3d@gmail.com',  # Email пользователя для аутентификации
                'service': 'invite-service',
                'iat': datetime.utcnow(),
                'exp': datetime.utcnow() + timedelta(hours=1)
            }
            
            self._jwt_token = jwt.encode(payload, jwt_secret, algorithm='HS256')
            self._jwt_expires_at = payload['exp']
            
            logger.debug("JWT токен для Integration Service обновлен")
            return self._jwt_token
            
        except Exception as e:
            logger.error(f"Ошибка получения JWT токена: {str(e)}")
            raise
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Выполнение HTTP запроса с retry логикой"""
        
        url = f"{self.base_url}{endpoint}"
        
        # Добавление JWT токена в заголовки
        if headers is None:
            headers = {}
        
        try:
            jwt_token = await self._get_jwt_token()
            headers['Authorization'] = f'Bearer {jwt_token}'
        except Exception as e:
            logger.warning(f"Не удалось получить JWT токен: {str(e)}")
        
        headers['Content-Type'] = 'application/json'
        headers['User-Agent'] = 'invite-service/1.0'
        
        # Retry логика
        last_exception = None
        
        for attempt in range(self.retry_config.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        json=json_data,
                        params=params,
                        headers=headers
                    )
                    
                    # Логирование запроса
                    logger.debug(
                        f"Integration Service {method} {endpoint}: "
                        f"status={response.status_code}, "
                        f"attempt={attempt + 1}"
                    )
                    
                    # Проверка статуса ответа
                    if response.status_code < 400:
                        return response.json()
                    
                    # Обработка ошибок
                    if response.status_code in [401, 403]:
                        # Проблемы с аутентификацией - обновляем токен
                        self._jwt_token = None
                        self._jwt_expires_at = None
                    
                    # Если это последняя попытка или не ретрайбл ошибка
                    if attempt == self.retry_config.max_retries or response.status_code < 500:
                        response.raise_for_status()
                    
                    # Логирование ошибки для retry
                    logger.warning(
                        f"Integration Service ошибка (retry {attempt + 1}): "
                        f"{response.status_code} - {response.text[:200]}"
                    )
                    
            except httpx.TimeoutException as e:
                last_exception = e
                logger.warning(f"Timeout при запросе к Integration Service (попытка {attempt + 1}): {str(e)}")
                
            except httpx.HTTPStatusError as e:
                # HTTP ошибки не ретраим, кроме 5xx
                if e.response.status_code < 500:
                    raise
                last_exception = e
                logger.warning(f"HTTP ошибка от Integration Service (попытка {attempt + 1}): {str(e)}")
                
            except Exception as e:
                last_exception = e
                logger.warning(f"Неожиданная ошибка при запросе к Integration Service (попытка {attempt + 1}): {str(e)}")
            
            # Задержка перед следующей попыткой
            if attempt < self.retry_config.max_retries:
                delay = min(
                    self.retry_config.base_delay * (self.retry_config.exponential_base ** attempt),
                    self.retry_config.max_delay
                )
                
                if self.retry_config.jitter:
                    import random
                    delay *= (0.5 + random.random() * 0.5)  # Jitter ±25%
                
                logger.debug(f"Ожидание {delay:.2f}s перед retry")
                await asyncio.sleep(delay)
        
        # Если все попытки исчерпаны
        logger.error(f"Все {self.retry_config.max_retries + 1} попыток к Integration Service исчерпаны")
        if last_exception:
            raise last_exception
        else:
            raise Exception("Неизвестная ошибка при обращении к Integration Service")
    
    async def get_user_accounts(self, user_id: int, platform: str = "telegram") -> List[Dict[str, Any]]:
        """Получение аккаунтов пользователя на платформе"""
        
        try:
            response = await self._make_request(
                method="GET",
                endpoint=f"/api/v1/{platform}/internal/active-accounts",
                params={"user_id": user_id}
            )
            
            logger.info(f"Получены аккаунты пользователя {user_id} на платформе {platform}: {len(response)} шт.")
            return response
            
        except Exception as e:
            logger.error(f"Ошибка получения аккаунтов пользователя {user_id} на {platform}: {str(e)}")
            raise
    
    async def send_telegram_invite(
        self,
        account_id: str,
        invite_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Отправка Telegram приглашения через Integration Service"""
        
        try:
            response = await self._make_request(
                method="POST",
                endpoint=f"/api/v1/telegram/accounts/{account_id}/invite",
                json_data=invite_data
            )
            
            logger.info(f"Telegram приглашение отправлено через аккаунт {account_id}")
            return response
            
        except Exception as e:
            logger.error(f"Ошибка отправки Telegram приглашения через аккаунт {account_id}: {str(e)}")
            raise
    
    async def send_telegram_message(
        self,
        account_id: str,
        message_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Отправка Telegram сообщения через Integration Service"""
        
        try:
            response = await self._make_request(
                method="POST",
                endpoint=f"/api/v1/telegram/accounts/{account_id}/message",
                json_data=message_data
            )
            
            logger.info(f"Telegram сообщение отправлено через аккаунт {account_id}")
            return response
            
        except Exception as e:
            logger.error(f"Ошибка отправки Telegram сообщения через аккаунт {account_id}: {str(e)}")
            raise
    
    async def get_account_limits(self, account_id: str) -> Dict[str, Any]:
        """Получение лимитов Telegram аккаунта"""
        
        try:
            response = await self._make_request(
                method="GET",
                endpoint=f"/api/v1/telegram/accounts/{account_id}/limits"
            )
            
            logger.debug(f"Получены лимиты для аккаунта {account_id}")
            return response
            
        except Exception as e:
            logger.error(f"Ошибка получения лимитов аккаунта {account_id}: {str(e)}")
            raise
    
    async def health_check(self) -> bool:
        """Проверка доступности Integration Service"""
        
        try:
            await self._make_request(
                method="GET",
                endpoint="/health"
            )
            return True
            
        except Exception as e:
            logger.warning(f"Integration Service недоступен: {str(e)}")
            return False
    
    async def close(self):
        """Очистка ресурсов клиента"""
        # Очистка JWT токена
        self._jwt_token = None
        self._jwt_expires_at = None
        logger.debug("Integration Service клиент закрыт")


# Глобальный экземпляр клиента (singleton)
_integration_client: Optional[IntegrationServiceClient] = None


def get_integration_client() -> IntegrationServiceClient:
    """Получение глобального экземпляра Integration Service клиента"""
    global _integration_client
    
    if _integration_client is None:
        _integration_client = IntegrationServiceClient()
    
    return _integration_client


async def close_integration_client():
    """Закрытие глобального клиента"""
    global _integration_client
    
    if _integration_client:
        await _integration_client.close()
        _integration_client = None 