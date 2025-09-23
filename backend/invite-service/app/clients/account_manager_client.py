"""Account Manager Client для Invite Service
Интеграция с централизованной системой управления Telegram аккаунтами

✅ СООТВЕТСТВУЕТ ТЗ ACCOUNT MANAGER:
- Все лимиты управляются только Account Manager
- Invite Service не имеет собственных лимитов
- Все паузы и ограничения определяются Account Manager
- Строгое соблюдение ТЗ: 15 инвайтов/день на паблик, 30/день на аккаунт, 200 на паблик НАВСЕГДА, паузы 10-15 минут
"""
import httpx
import logging
from typing import Optional, Dict, Any, List
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
        purpose: str = "invite_campaign",
        preferred_account_id: Optional[str] = None,
        timeout_minutes: int = 30
    ) -> Optional[Dict[str, Any]]:
        """
        ✅ СООТВЕТСТВУЕТ ТЗ: Выделить аккаунт для приглашений
        
        Account Manager самостоятельно проверяет ВСЕ лимиты согласно ТЗ:
        - Статус аккаунта (active)
        - Лимиты инвайтов: 15/день на один паблик, 30/день на весь аккаунт, 200 на паблик НАВСЕГДА
        - Лимиты сообщений: 30/день
        - FloodWait, BlockedUntil
        - Устанавливает locked = true
        
        Args:
            user_id: ID пользователя
            purpose: Цель использования (invite_campaign)
            preferred_account_id: Предпочтительный аккаунт
            timeout_minutes: Таймаут блокировки в минутах
            
        Returns:
            Dict с данными аккаунта или None если нет доступных
        """
        try:
            logger.info(f"🔍 AccountManager: Requesting account allocation for user {user_id}, purpose: {purpose} (все лимиты управляются Account Manager согласно ТЗ)")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/allocate",
                    json={
                        "user_id": user_id,
                        "purpose": purpose,
                        "service_name": "invite-service",
                        "preferred_account_id": preferred_account_id,
                        "timeout_minutes": timeout_minutes
                    }
                )
                
                if response.status_code == 200:
                    allocation = response.json()
                    logger.info(f"✅ AccountManager: Account allocated: {allocation['account_id']}, phone: {allocation['phone']} (лимиты проверены Account Manager)")
                    return allocation
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
            logger.info(f"🔓 AccountManager: Releasing account {account_id} (обновление лимитов в Account Manager)")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/release/{account_id}",
                    json={
                        "service_name": "invite-service",
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
        ✅ СООТВЕТСТВУЕТ ТЗ: Обработать ошибку аккаунта
        
        Account Manager обрабатывает ошибки согласно ТЗ:
        - FloodWaitError: устанавливает flood_wait_until, status = "flood_wait"
        - PeerFloodError, AuthKeyError: status = "blocked"
        - Автоматическое восстановление по крону
        
        Args:
            account_id: ID аккаунта
            error_type: Тип ошибки (flood_wait, peer_flood, etc.)
            error_message: Сообщение об ошибке
            context: Дополнительный контекст
            
        Returns:
            bool: Успешность обработки
        """
        try:
            logger.warning(f"⚠️ AccountManager: Handling error for account {account_id}: {error_type} (согласно ТЗ Account Manager)")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/handle-error/{account_id}",
                    json={
                        "error_type": error_type,
                        "error_message": error_message,
                        "context": context or {"service": "invite-service"}
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
    
    async def check_rate_limit(
        self,
        account_id: str,
        action_type: str = "invite",
        target_channel_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        ✅ КЛЮЧЕВАЯ ФУНКЦИЯ ТЗ: Проверить rate limits перед действием
        
        Account Manager проверяет ВСЕ лимиты согласно ТЗ:
        - Инвайты: 15/день на один паблик, 30/день на весь аккаунт, 200 на паблик НАВСЕГДА
        - Паузы: 10-15 минут между инвайтами
        - Сообщения: 30/день, паузы 1-2 минуты
        - Контакты: 15/день, потом 5/день
        - ВАЖНО: После 200 приглашений в конкретный паблик аккаунт больше не может приглашать в ЭТОТ паблик
        
        Args:
            account_id: ID аккаунта
            action_type: Тип действия (invite, message, add_contact)
            target_channel_id: ID целевого канала
            
        Returns:
            Dict со статусом лимитов и необходимыми паузами
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/rate-limit/check/{account_id}",
                    json={
                        "action_type": action_type,
                        "target_channel_id": target_channel_id
                    }
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"❌ Failed to check rate limits: {response.status_code}")
                    return {"allowed": False, "reason": "Rate limit check failed"}
                    
        except Exception as e:
            logger.error(f"❌ Error checking rate limits: {e}")
            return {"allowed": False, "reason": f"Error: {e}"}
    
    async def record_action(
        self,
        account_id: str,
        action_type: str = "invite",
        target_channel_id: Optional[str] = None,
        success: bool = True
    ) -> bool:
        """
        Записать выполненное действие
        
        Args:
            account_id: ID аккаунта
            action_type: Тип действия
            target_channel_id: ID целевого канала
            success: Успешность действия
            
        Returns:
            bool: Успешность записи
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/rate-limit/record/{account_id}",
                    json={
                        "action_type": action_type,
                        "target_channel_id": target_channel_id,
                        "success": success
                    }
                )
                
                return response.status_code == 200
                    
        except Exception as e:
            logger.error(f"❌ Error recording action: {e}")
            return False
    
    async def get_account_health(self, account_id: str) -> Optional[Dict[str, Any]]:
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
    
    async def get_recovery_stats(self) -> Optional[Dict[str, Any]]:
        """
        Получить статистику восстановления аккаунтов
        
        Returns:
            Dict со статистикой или None при ошибке
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/stats/recovery")
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"❌ Failed to get recovery stats: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Error getting recovery stats: {e}")
            return None
    
    async def get_available_accounts(self, user_id: int, purpose: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Получить список доступных аккаунтов пользователя из Account Manager."""
        try:
            params = {}
            if purpose:
                params["purpose"] = purpose
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/available-accounts/{user_id}", params=params
                )
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"❌ Failed to get available accounts for user {user_id}: {response.status_code} - {response.text}")
                    return None
        except Exception as e:
            logger.error(f"❌ Error getting available accounts: {e}")
            return None

    async def get_accounts_summary(
        self,
        user_id: int,
        purpose: Optional[str] = None,
        target_channel_id: Optional[str] = None,
        limit: int = 500,
    ) -> Optional[Dict[str, Any]]:
        """Получить агрегированную витрину аккаунтов пользователя из Account Manager."""
        try:
            params: Dict[str, Any] = {"user_id": user_id, "limit": limit}
            if purpose:
                params["purpose"] = purpose
            if target_channel_id:
                params["target_channel_id"] = target_channel_id

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/accounts/summary", params=params)
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(
                        f"❌ Failed to get accounts summary for user {user_id}: {response.status_code} - {response.text}"
                    )
                    return None
        except Exception as e:
            logger.error(f"❌ Error getting accounts summary: {e}")
            return None
    
    async def release_all_accounts(self) -> Dict[str, Any]:
        """
        Освободить все аккаунты, заблокированные данным сервисом
        
        Returns:
            Dict с результатами операции
        """
        try:
            logger.info(f"🔓 Releasing all accounts locked by invite-service")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/release-all",
                    json={
                        "service_name": "invite-service",
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