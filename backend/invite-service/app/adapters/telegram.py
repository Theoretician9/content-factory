"""
Telegram Platform Adapter для приглашений через Integration Service
Интегрирован с Account Manager для централизованного управления аккаунтами
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import httpx

from .base import (
    InvitePlatformAdapter,
    PlatformAccount,
    InviteResult,
    RateLimitStatus,
    InviteResultStatus,
    AccountStatus
)
from app.services.integration_client import IntegrationServiceClient
from app.clients.account_manager_client import AccountManagerClient

logger = logging.getLogger(__name__)


class TelegramInviteAdapter(InvitePlatformAdapter):
    """Адаптер для приглашений в Telegram через Integration Service
    Интегрирован с Account Manager для централизованного управления аккаунтами
    """
    
    def __init__(self):
        super().__init__("telegram")
        self.integration_client = IntegrationServiceClient()
        self.account_manager = AccountManagerClient()
        self.allocated_accounts = {}  # Кэш выделенных аккаунтов
        
        # Стандартные лимиты Telegram (соответствуют Account Manager)
        self.default_limits = {
            "daily_invite_limit": 30,      # Соответствует Account Manager
            "daily_message_limit": 30,     # Соответствует Account Manager
            "hourly_invite_limit": 2,      # Соответствует Account Manager
            "per_channel_daily_limit": 15, # Соответствует Account Manager
            "max_per_channel_total": 200,  # Максимум на канал с одного аккаунта
            "flood_wait_buffer": 300       # 5 минут буфер после flood wait
        }
    
    async def initialize_accounts(self, user_id: int) -> List[PlatformAccount]:
        """Получение Telegram аккаунтов пользователя через Account Manager"""
        
        try:
            logger.info(f"🔍 Инициализация Telegram аккаунтов для пользователя {user_id} через Account Manager")
            
            # Получаем базовую информацию о доступных аккаунтах
            accounts_data = await self.integration_client.get_user_accounts(
                user_id=user_id,
                platform="telegram"
            )
            
            if not accounts_data:
                logger.warning(f"⚠️ Нет доступных Telegram аккаунтов для пользователя {user_id}")
                return []
            
            platform_accounts = []
            
            for acc_data in accounts_data:
                # Преобразование в PlatformAccount с лимитами Account Manager
                account = PlatformAccount(
                    account_id=acc_data["id"],
                    username=acc_data.get("username"),
                    phone=acc_data.get("phone"),
                    status=AccountStatus.ACTIVE if acc_data.get("status") == "active" else AccountStatus.INACTIVE,
                    platform="telegram",
                    
                    # Лимиты соответствуют Account Manager
                    daily_invite_limit=self.default_limits["daily_invite_limit"],
                    daily_message_limit=self.default_limits["daily_message_limit"],
                    hourly_invite_limit=self.default_limits["hourly_invite_limit"],
                    
                    # Дополнительные данные
                    last_activity=acc_data.get("last_activity"),
                    extra_data={
                        "first_name": acc_data.get("first_name"),
                        "last_name": acc_data.get("last_name"),
                        "created_at": acc_data.get("created_at"),
                        "user_id": user_id  # Для Account Manager
                    }
                )
                
                # TODO: Временно отключена проверка здоровья через Account Manager
                # т.к. endpoint /health/{account_id} может работать неправильно
                # health_status = await self.account_manager.get_account_health(str(account.account_id))
                # if health_status:
                #     if not health_status.get("is_healthy", True):
                #         account.status = AccountStatus.INACTIVE
                #         logger.warning(f"⚠️ Аккаунт {account.account_id} нездоров: {health_status.get('issues', [])}")
                
                platform_accounts.append(account)
            
            # Фильтрация только активных аккаунтов
            active_accounts = [acc for acc in platform_accounts if acc.status == AccountStatus.ACTIVE]
            
            logger.info(f"✅ Инициализированы Telegram аккаунты для пользователя {user_id}: {len(active_accounts)} активных из {len(platform_accounts)}")
            
            return active_accounts
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Telegram аккаунтов для пользователя {user_id}: {str(e)}")
            raise
    
    async def send_invite(
        self,
        account: PlatformAccount,
        target: Dict[str, Any],
        invite_data: Dict[str, Any]
    ) -> InviteResult:
        """Отправка приглашения через Integration Service"""
        
        start_time = datetime.utcnow()
        
        # Проверка возможности отправки
        if not account.can_send_invite():
            return InviteResult(
                status=InviteResultStatus.RATE_LIMITED,
                error_message="Аккаунт достиг лимита приглашений",
                account_id=account.account_id,
                can_retry=True,
                retry_after=self._calculate_retry_time(account)
            )
        
        try:
            # Подготовка данных для Integration Service
            telegram_invite_data = {
                "invite_type": invite_data.get("invite_type", "group_invite"),
                "target_username": target.get("username"),
                "target_phone": target.get("phone_number"),
                "target_user_id": target.get("user_id_platform"),
                "group_id": invite_data.get("group_id"),
                "message": invite_data.get("message"),
                "parse_mode": invite_data.get("parse_mode", "text"),
                "silent": invite_data.get("silent", False)
            }
            
            # Отправка через Integration Service
            response = await self.integration_client.send_telegram_invite(
                account_id=account.account_id,
                invite_data=telegram_invite_data
            )
            
            # Обработка успешного ответа
            end_time = datetime.utcnow()
            execution_time = (end_time - start_time).total_seconds()
            
            result = InviteResult(
                status=InviteResultStatus.SUCCESS,
                message="Приглашение отправлено успешно",
                message_id=response.get("message_id"),
                target_username=target.get("username"),
                target_phone=target.get("phone_number"),
                sent_at=end_time,
                execution_time=execution_time,
                account_id=account.account_id,
                platform_response=response
            )
            
            # Обновление статистики аккаунта
            await self.update_account_stats(account, result)
            
            return result
            
        except httpx.HTTPStatusError as e:
            # Обработка HTTP ошибок от Integration Service
            return await self._handle_integration_service_error(e, account, start_time)
            
        except Exception as e:
            # Общие ошибки
            logger.error(f"Ошибка отправки Telegram приглашения: {str(e)}")
            return InviteResult(
                status=InviteResultStatus.NETWORK_ERROR,
                error_message=f"Ошибка сети: {str(e)}",
                account_id=account.account_id,
                execution_time=(datetime.utcnow() - start_time).total_seconds(),
                can_retry=True
            )
    
    async def send_message(
        self,
        account: PlatformAccount,
        target: Dict[str, Any],
        message_data: Dict[str, Any]
    ) -> InviteResult:
        """Отправка прямого сообщения через Integration Service"""
        
        start_time = datetime.utcnow()
        
        # Проверка возможности отправки
        if not account.can_send_message():
            return InviteResult(
                status=InviteResultStatus.RATE_LIMITED,
                error_message="Аккаунт достиг лимита сообщений",
                account_id=account.account_id,
                can_retry=True,
                retry_after=self._calculate_retry_time(account)
            )
        
        try:
            # Подготовка данных для сообщения
            telegram_message_data = {
                "target_entity": target.get("username") or target.get("phone_number") or target.get("user_id_platform"),
                "message": message_data.get("message"),
                "parse_mode": message_data.get("parse_mode", "text"),
                "silent": message_data.get("silent", False),
                "reply_to_message_id": message_data.get("reply_to_message_id")
            }
            
            # Отправка через Integration Service
            response = await self.integration_client.send_telegram_message(
                account_id=account.account_id,
                message_data=telegram_message_data
            )
            
            # Обработка успешного ответа
            end_time = datetime.utcnow()
            execution_time = (end_time - start_time).total_seconds()
            
            result = InviteResult(
                status=InviteResultStatus.SUCCESS,
                message="Сообщение отправлено успешно",
                message_id=response.get("message_id"),
                target_username=target.get("username"),
                target_phone=target.get("phone_number"),
                sent_at=end_time,
                execution_time=execution_time,
                account_id=account.account_id,
                platform_response=response
            )
            
            # Обновление статистики
            account.daily_messages_used += 1
            account.last_activity = datetime.utcnow()
            
            return result
            
        except httpx.HTTPStatusError as e:
            return await self._handle_integration_service_error(e, account, start_time)
            
        except Exception as e:
            logger.error(f"Ошибка отправки Telegram сообщения: {str(e)}")
            return InviteResult(
                status=InviteResultStatus.NETWORK_ERROR,
                error_message=f"Ошибка сети: {str(e)}",
                account_id=account.account_id,
                execution_time=(datetime.utcnow() - start_time).total_seconds(),
                can_retry=True
            )
    
    async def check_rate_limits(self, account: PlatformAccount) -> RateLimitStatus:
        """Проверка текущих rate limits через Integration Service"""
        
        try:
            # Получение лимитов через Integration Service
            limits_data = await self.integration_client.get_account_limits(account.account_id)
            
            current_usage = limits_data.get("current_usage", {})
            limits = limits_data.get("limits", {})
            
            # Вычисление оставшихся лимитов
            invites_remaining_daily = max(0, limits.get("daily_invites", 50) - current_usage.get("daily_invites_used", 0))
            invites_remaining_hourly = max(0, limits.get("hourly_invites", 5) - current_usage.get("hourly_invites_used", 0))
            messages_remaining_daily = max(0, limits.get("daily_messages", 40) - current_usage.get("daily_messages_used", 0))
            
            # Проверка flood wait
            flood_wait_until = None
            restrictions = limits_data.get("restrictions", [])
            
            if limits.get("flood_wait_active"):
                flood_wait_until = datetime.utcnow() + timedelta(seconds=self.default_limits["flood_wait_buffer"])
            
            return RateLimitStatus(
                can_send_invite=invites_remaining_daily > 0 and invites_remaining_hourly > 0 and not flood_wait_until,
                can_send_message=messages_remaining_daily > 0 and not flood_wait_until,
                invites_remaining_daily=invites_remaining_daily,
                invites_remaining_hourly=invites_remaining_hourly,
                messages_remaining_daily=messages_remaining_daily,
                daily_reset_at=datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1),
                hourly_reset_at=datetime.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1),
                flood_wait_until=flood_wait_until,
                restrictions=restrictions
            )
            
        except Exception as e:
            logger.error(f"Ошибка проверки rate limits для аккаунта {account.account_id}: {str(e)}")
            
            # Возвращаем консервативные лимиты при ошибке
            return RateLimitStatus(
                can_send_invite=True,
                can_send_message=True,
                invites_remaining_daily=0,  # Консервативно
                invites_remaining_hourly=0,
                messages_remaining_daily=0,
                daily_reset_at=datetime.utcnow() + timedelta(days=1),
                hourly_reset_at=datetime.utcnow() + timedelta(hours=1),
                restrictions=["rate_check_failed"]
            )
    
    async def validate_target(self, target: Dict[str, Any]) -> bool:
        """Валидация целевого пользователя"""
        
        # Проверка наличия хотя бы одного идентификатора
        identifiers = [
            target.get("username"),
            target.get("phone_number"),
            target.get("user_id_platform")
        ]
        
        if not any(identifiers):
            return False
        
        # Валидация username (без @, только буквы, цифры, подчеркивания)
        username = target.get("username")
        if username:
            if username.startswith("@"):
                username = username[1:]
            
            if not username.replace("_", "").isalnum():
                return False
            
            if len(username) < 5 or len(username) > 32:
                return False
        
        # Валидация номера телефона
        phone = target.get("phone_number")
        if phone:
            # Простая валидация - только цифры и +
            clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
            if not clean_phone.isdigit() or len(clean_phone) < 10:
                return False
        
        return True
    
    async def _handle_integration_service_error(
        self,
        error: httpx.HTTPStatusError,
        account: PlatformAccount,
        start_time: datetime
    ) -> InviteResult:
        """Обработка ошибок от Integration Service"""
        
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        
        try:
            error_data = error.response.json()
        except:
            error_data = {"detail": str(error)}
        
        if error.response.status_code == 429:
            # Rate limiting или Flood Wait
            detail = error_data.get("detail", {})
            
            if isinstance(detail, dict):
                if detail.get("error") == "flood_wait":
                    # Telegram FloodWait
                    seconds = detail.get("seconds", 300)
                    retry_after = datetime.utcnow() + timedelta(seconds=seconds + self.default_limits["flood_wait_buffer"])
                    
                    # Обновление аккаунта
                    account.flood_wait_until = retry_after
                    account.status = AccountStatus.FLOOD_WAIT
                    
                    return InviteResult(
                        status=InviteResultStatus.FLOOD_WAIT,
                        error_message=f"Telegram FloodWait: {seconds} секунд",
                        error_code="flood_wait",
                        retry_after=retry_after,
                        execution_time=execution_time,
                        account_id=account.account_id,
                        can_retry=True
                    )
                
                elif detail.get("error") == "peer_flood":
                    # PeerFlood - слишком много запросов к пользователям
                    account.status = AccountStatus.RATE_LIMITED
                    
                    return InviteResult(
                        status=InviteResultStatus.PEER_FLOOD,
                        error_message="Слишком много запросов к пользователям",
                        error_code="peer_flood",
                        retry_after=datetime.utcnow() + timedelta(hours=24),
                        execution_time=execution_time,
                        account_id=account.account_id,
                        can_retry=False  # PeerFlood обычно на долго
                    )
            
            # Общий rate limiting
            return InviteResult(
                status=InviteResultStatus.RATE_LIMITED,
                error_message="Превышен лимит запросов",
                error_code="rate_limited",
                retry_after=datetime.utcnow() + timedelta(hours=1),
                execution_time=execution_time,
                account_id=account.account_id,
                can_retry=True
            )
        
        elif error.response.status_code == 403:
            # Privacy restrictions
            detail = error_data.get("detail", {})
            
            if isinstance(detail, dict) and detail.get("error") == "privacy_restricted":
                return InviteResult(
                    status=InviteResultStatus.PRIVACY_RESTRICTED,
                    error_message="Настройки приватности запрещают приглашения",
                    error_code="privacy_restricted",
                    execution_time=execution_time,
                    account_id=account.account_id,
                    can_retry=False
                )
        
        elif error.response.status_code == 400:
            # Bad request - различные ошибки
            detail = error_data.get("detail", {})
            
            if isinstance(detail, dict):
                error_type = detail.get("error", "unknown")
                
                if error_type == "not_mutual_contact":
                    return InviteResult(
                        status=InviteResultStatus.NOT_MUTUAL_CONTACT,
                        error_message="Пользователь должен быть в контактах",
                        error_code="not_mutual_contact",
                        execution_time=execution_time,
                        account_id=account.account_id,
                        can_retry=False
                    )
        
        # Общая ошибка
        return InviteResult(
            status=InviteResultStatus.FAILED,
            error_message=f"Ошибка Integration Service: {error_data.get('detail', str(error))}",
            error_code=f"http_{error.response.status_code}",
            execution_time=execution_time,
            account_id=account.account_id,
            can_retry=error.response.status_code >= 500  # Ретрай только для server errors
        )
    
    def _calculate_retry_time(self, account: PlatformAccount) -> datetime:
        """Вычисление времени для повторной попытки"""
        
        if account.flood_wait_until:
            return account.flood_wait_until
        
        # Если достигнут дневной лимит - ждем до следующего дня
        if account.daily_invites_used >= account.daily_invite_limit:
            tomorrow = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            return tomorrow
        
        # Если достигнут часовой лимит - ждем до следующего часа
        if account.hourly_invites_used >= account.hourly_invite_limit:
            next_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            return next_hour
        
        # По умолчанию - через час
        return datetime.utcnow() + timedelta(hours=1) 