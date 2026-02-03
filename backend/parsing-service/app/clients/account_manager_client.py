"""
Account Manager Client для Parsing Service
Интеграция с централизованной системой управления Telegram аккаунтами
"""
import httpx
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from ..core.config import get_settings

logger = logging.getLogger(__name__)

class AccountManagerClient:
    """HTTP клиент для взаимодействия с Account Manager в Integration Service"""
    
    def __init__(self):
        self.settings = get_settings()
        self.base_url = "http://integration-service:8000/api/v1/account-manager"
        self.timeout = 30.0
        
    async def allocate_account(
        self, 
        user_id: int, 
        purpose: str = "parsing",
        timeout_minutes: int = 60
    ) -> Optional[Dict[str, Any]]:
        """
        Выделить аккаунт для парсинга
        
        Args:
            user_id: ID пользователя
            purpose: Цель использования (parsing)
            timeout_minutes: Таймаут блокировки в минутах
            
        Returns:
            Dict с данными аккаунта или None если нет доступных
        """
        try:
            logger.info(f"🔍 Requesting account allocation for user {user_id}, purpose: {purpose}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/allocate",
                    json={
                        "user_id": user_id,
                        "purpose": purpose,
                        "service_name": "parsing-service",
                        "timeout_minutes": timeout_minutes
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success') and 'allocation' in data:
                        allocation = data['allocation']
                        logger.info(f"✅ Account allocated: {allocation['account_id']}, phone: {allocation['phone']}")
                        return allocation
                    else:
                        logger.error(f"❌ Unexpected response format: {data}")
                        return None
                elif response.status_code == 404:
                    logger.warning(f"❌ No available accounts for user {user_id}")
                    return None
                else:
                    logger.error(f"❌ Account allocation failed: {response.status_code} - {response.text}")
                    response.raise_for_status()
                    
        except Exception as e:
            logger.error(f"❌ Error allocating account: {e}")
            return None
    
    async def release_account(
        self,
        account_id: str,
        usage_stats: Dict[str, Any]
    ) -> bool:
        """
        Освободить аккаунт после использования
        
        Args:
            account_id: ID аккаунта
            usage_stats: Статистика использования
            
        Returns:
            bool: Успешность операции
        """
        try:
            logger.info(f"🔓 Releasing account {account_id}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/release/{account_id}",
                    json={
                        "service_name": "parsing-service",
                        "usage_stats": usage_stats
                    }
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Account {account_id} released successfully")
                    return True
                else:
                    logger.error(f"❌ Failed to release account {account_id}: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error releasing account {account_id}: {e}")
            return False
    
    async def handle_error(
        self,
        account_id: str,
        error_type: str,
        error_message: str,
        context: Dict[str, Any] = None
    ) -> bool:
        """
        Обработать ошибку аккаунта
        
        Args:
            account_id: ID аккаунта
            error_type: Тип ошибки (flood_wait, auth_key_error, etc.)
            error_message: Сообщение об ошибке
            context: Дополнительный контекст
            
        Returns:
            bool: Успешность обработки
        """
        try:
            logger.warning(f"⚠️ Handling error for account {account_id}: {error_type}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/handle-error/{account_id}",
                    json={
                        "error_type": error_type,
                        "error_message": error_message,
                        "context": context or {"service": "parsing-service"}
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"✅ Error handled: {result.get('action_taken', 'Unknown action')}")
                    return True
                else:
                    logger.error(f"❌ Failed to handle error: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error handling account error: {e}")
            return False
    
    async def check_account_health(self, account_id: str) -> Optional[Dict[str, Any]]:
        """
        Проверить здоровье аккаунта
        
        Args:
            account_id: ID аккаунта
            
        Returns:
            Dict со статусом здоровья или None при ошибке
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/health/{account_id}")
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"❌ Failed to check account health: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Error checking account health: {e}")
            return None
    
    async def release_all_accounts(self) -> Dict[str, Any]:
        """
        Освободить все аккаунты, заблокированные данным сервисом
        
        Returns:
            Dict с результатами операции
        """
        try:
            logger.info(f"🔓 Releasing all accounts locked by parsing-service")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/release-all",
                    json={
                        "service_name": "parsing-service",
                        "force": True
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"✅ Released {result.get('released_count', 0)} accounts")
                    return result
                else:
                    logger.error(f"❌ Failed to release all accounts: {response.status_code} - {response.text}")
                    return {"error": f"HTTP {response.status_code}", "details": response.text}
                    
        except Exception as e:
            logger.error(f"❌ Error releasing all accounts: {e}")
            return {"error": str(e)}

    async def check_rate_limit(
        self,
        account_id: str,
        action_type: str = "parse",
        target_channel_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Проверить rate limits в Account Manager перед действием парсинга.
        По умолчанию используем action_type="parse". AM возвращает статус и, при необходимости, время ожидания.
        """
        try:
            payload = {
                "action_type": action_type,
                "service_name": "parsing-service"
            }
            if target_channel_id:
                payload["target_channel_id"] = target_channel_id

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/limits/check/{account_id}",
                    json=payload
                )

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"✅ Rate limit check for {account_id}: {data}")
                    return data
                else:
                    logger.error(f"❌ Rate limit check failed: {response.status_code} - {response.text}")
                    return None
        except Exception as e:
            logger.error(f"❌ Error checking rate limit for {account_id}: {e}")
            return None