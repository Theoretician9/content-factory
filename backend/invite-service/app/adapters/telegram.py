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
            
            # 🔍 ДИАГНОСТИКА: логируем сырой ответ от integration-service
            logger.info(f"🔍 Ответ от integration-service: {len(accounts_data) if accounts_data else 0} аккаунтов")
            if accounts_data:
                for i, acc in enumerate(accounts_data):
                    logger.info(f"🔍   Сырой аккаунт {i+1}: {acc}")
            
            if not accounts_data:
                logger.warning(f"⚠️ Нет доступных Telegram аккаунтов для пользователя {user_id}")
                return []
            
            platform_accounts = []
            
            for acc_data in accounts_data:
                # 🔍 ДИАГНОСТИКА: логируем сырые данные аккаунта
                logger.info(f"🔍 Обработка аккаунта {acc_data.get('id')}: is_active='{acc_data.get('is_active')}', username='{acc_data.get('username')}', phone='{acc_data.get('phone')}'")
                
                # Преобразование в PlatformAccount с лимитами Account Manager
                # ИСПРАВЛЕНО: используем is_active вместо status
                is_active = acc_data.get("is_active", False)
                account_status = AccountStatus.ACTIVE if is_active else AccountStatus.INACTIVE
                
                logger.info(f"🔍 Аккаунт {acc_data.get('id')}: is_active='{is_active}' -> account_status={account_status}")
                
                account = PlatformAccount(
                    account_id=acc_data["id"],
                    username=acc_data.get("username"),
                    phone=acc_data.get("phone"),
                    status=account_status,
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
            
            # 🔍 ДИАГНОСТИКА: логируем все аккаунты перед фильтрацией
            logger.info(f"🔍 Всего создано {len(platform_accounts)} аккаунтов PlatformAccount:")
            for i, acc in enumerate(platform_accounts):
                logger.info(f"🔍   Аккаунт {i+1}: id={acc.account_id}, status={acc.status}, username={acc.username}")
            
            # Фильтрация только активных аккаунтов
            active_accounts = [acc for acc in platform_accounts if acc.status == AccountStatus.ACTIVE]
            
            # 🔍 ДИАГНОСТИКА: логируем результат фильтрации
            logger.info(f"🔍 После фильтрации осталось {len(active_accounts)} активных аккаунтов:")
            for i, acc in enumerate(active_accounts):
                logger.info(f"🔍   Активный {i+1}: id={acc.account_id}, username={acc.username}")
            
            # 🔍 Проверяем статус AccountStatus.ACTIVE
            logger.info(f"🔍 AccountStatus.ACTIVE = {AccountStatus.ACTIVE}")
            
            logger.info(f"✅ Инициализированы Telegram аккаунты для пользователя {user_id}: {len(active_accounts)} активных из {len(platform_accounts)}")
            
            return active_accounts
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Telegram аккаунтов для пользователя {user_id}: {str(e)}")
            raise
    
    async def validate_target(self, target_data: Dict[str, Any]) -> bool:
        """Валидация данных цели для Telegram приглашения"""
        # Проверяем, что цель имеет хотя бы один идентификатор
        username = target_data.get("username")
        phone = target_data.get("phone_number")
        user_id = target_data.get("user_id_platform")
        
        # 🔍 ДИАГНОСТИКА: подробная информация о данных цели для валидации
        logger.info(f"🔍 DIAGNOSTIC: Валидация цели:")
        logger.info(f"🔍 DIAGNOSTIC:   username: {repr(username)} (empty: {not username or not str(username).strip()})")
        logger.info(f"🔍 DIAGNOSTIC:   phone_number: {repr(phone)} (empty: {not phone or not str(phone).strip()})")
        logger.info(f"🔍 DIAGNOSTIC:   user_id_platform: {repr(user_id)} (empty: {not user_id or not str(user_id).strip()})")
        
        # Проверяем, есть ли хотя бы один непустой идентификатор
        has_valid_username = username and str(username).strip()
        has_valid_phone = phone and str(phone).strip()
        has_valid_user_id = user_id and str(user_id).strip()
        
        logger.info(f"🔍 DIAGNOSTIC:   has_valid_username: {has_valid_username}")
        logger.info(f"🔍 DIAGNOSTIC:   has_valid_phone: {has_valid_phone}")
        logger.info(f"🔍 DIAGNOSTIC:   has_valid_user_id: {has_valid_user_id}")
        logger.info(f"🔍 DIAGNOSTIC:   any valid identifier: {any([has_valid_username, has_valid_phone, has_valid_user_id])}")
        
        # ✅ ИЗМЕНЕНО: Более строгая проверка
        if not any([has_valid_username, has_valid_phone, has_valid_user_id]):
            logger.warning("Цель не содержит идентификатора для Telegram приглашения")
            return False
        
        # Дополнительная валидация формата данных
        if username and not isinstance(username, str):
            logger.warning("Некорректный формат username")
            return False
            
        if phone and not isinstance(phone, str):
            logger.warning("Некорректный формат phone_number")
            return False
            
        if user_id and not isinstance(user_id, str):
            logger.warning("Некорректный формат user_id_platform")
            return False
        
        logger.debug(f"Цель прошла валидацию: username={username}, phone={phone}, user_id={user_id}")
        return True
    
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
            // Проверяем, что у цели есть хотя бы один идентификатор
            target_username = target.get("username")
            target_phone = target.get("phone_number")
            target_user_id = target.get("user_id_platform")
            
            // 🔍 ДИАГНОСТИКА: подробное логирование данных цели
            logger.info(f"🔍 DIAGNOSTIC: Подробные данные цели перед валидацией:")
            logger.info(f"🔍 DIAGNOSTIC:   username: {repr(target_username)} (type: {type(target_username)})")
            logger.info(f"🔍 DIAGNOSTIC:   phone_number: {repr(target_phone)} (type: {type(target_phone)})")
            logger.info(f"🔍 DIAGNOSTIC:   user_id_platform: {repr(target_user_id)} (type: {type(target_user_id)})")
            logger.info(f"🔍 DIAGNOSTIC:   any identifiers: {any([target_username, target_phone, target_user_id])}")
            
            // ✅ ДОБАВЛЕНО: Более строгая проверка перед отправкой
            if not any([target_username, target_phone, target_user_id]):
                error_msg = "Цель не содержит идентификатора (username, phone_number или user_id_platform)"
                logger.error(f"❌ {error_msg}")
                return InviteResult(
                    status=InviteResultStatus.FAILED,
                    error_message=error_msg,
                    account_id=account.account_id,
                    can_retry=False
                )
            
            // Подготовка данных для Integration Service
            telegram_invite_data = {
                "invite_type": invite_data.get("invite_type", "group_invite"),
                "target_username": target_username,
                "target_phone": target_phone,
                "target_user_id": target_user_id,
                "group_id": invite_data.get("group_id"),
                "message": invite_data.get("message"),
                "parse_mode": invite_data.get("parse_mode", "text"),
                "silent": invite_data.get("silent", False)
            }
            
            // 🔍 ДИАГНОСТИКА: логируем данные, отправляемые в Integration Service
            logger.info(f"🔍 DIAGNOSTIC: Данные для Integration Service:")
            for key, value in telegram_invite_data.items():
                logger.info(f"🔍 DIAGNOSTIC:   {key}: {repr(value)}")
            
            // ✅ ДОБАВЛЕНО: Проверяем, что хотя бы одно из полей target_* заполнено
            target_fields = [target_username, target_phone, target_user_id]
            if not any(field is not None and str(field).strip() for field in target_fields):
                error_msg = "Цель не содержит корректных идентификаторов для приглашения"
                logger.error(f"❌ {error_msg}")
                logger.error(f"❌ Данные цели: username={repr(target_username)}, phone={repr(target_phone)}, user_id={repr(target_user_id)}")
                return InviteResult(
                    status=InviteResultStatus.FAILED,
                    error_message=error_msg,
                    account_id=account.account_id,
                    can_retry=False
                )
            
            // Отправка через Integration Service
            response = await self.integration_client.send_telegram_invite(
                account_id=account.account_id,
                invite_data=telegram_invite_data
            )
            
            // Обработка успешного ответа
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
            
            // Обновление статистики аккаунта
            await self.update_account_stats(account, result)
            
            return result
            
        except httpx.HTTPStatusError as e:
            // Обработка HTTP ошибок от Integration Service
            return await self._handle_integration_service_error(e, account, start_time)
            
        except Exception as e:
            // Общие ошибки
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
        
        // Проверка возможности отправки
        if not account.can_send_message():
            return InviteResult(
                status=InviteResultStatus.RATE_LIMITED,
                error_message="Аккаунт достиг лимита сообщений",
                account_id=account.account_id,
                can_retry=True,
                retry_after=self._calculate_retry_time(account)
            )
        
        try:
            // Подготовка данных для сообщения
            telegram_message_data = {
                "target_entity": target.get("username") or target.get("phone_number") or target.get("user_id_platform"),
                "message": message_data.get("message"),
                "parse_mode": message_data.get("parse_mode", "text"),
                "silent": message_data.get("silent", False),
                "reply_to_message_id": message_data.get("reply_to_message_id")
            }
            
            // Отправка через Integration Service
            response = await self.integration_client.send_telegram_message(
                account_id=account.account_id,
                message_data=telegram_message_data
            )
            
            // Обработка успешного ответа
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
            
            // Обновление статистики
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
            // Получение лимитов через Integration Service
            limits_data = await self.integration_client.get_account_limits(account.account_id)
            
            current_usage = limits_data.get("current_usage", {})
            limits = limits_data.get("limits", {})
            
            // Вычисление оставшихся лимитов
            invites_remaining_daily = max(0, limits.get("daily_invites", 50) - current_usage.get("daily_invites_used", 0))
            invites_remaining_hourly = max(0, limits.get("hourly_invites", 5) - current_usage.get("hourly_invites_used", 0))
            messages_remaining_daily = max(0, limits.get("daily_messages", 40) - current_usage.get("daily_messages_used", 0))
            
            // Проверка flood wait
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
            
            // Возвращаем консервативные лимиты при ошибке
            return RateLimitStatus(
                can_send_invite=True,
                can_send_message=True,
                invites_remaining_daily=0,  // Консервативно
                invites_remaining_hourly=0,
                messages_remaining_daily=0,
                daily_reset_at=datetime.utcnow() + timedelta(days=1),
                hourly_reset_at=datetime.utcnow() + timedelta(hours=1),
                restrictions=["rate_check_failed"]
            )
    
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
            // Rate limiting или Flood Wait
            detail = error_data.get("detail", {})
            
            if isinstance(detail, dict):
                if detail.get("error") == "flood_wait":
                    // Telegram FloodWait
                    seconds = detail.get("seconds", 300)
                    retry_after = datetime.utcnow() + timedelta(seconds=seconds + self.default_limits["flood_wait_buffer"])
                    
                    // Обновление аккаунта
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
                    // PeerFlood - слишком много запросов к пользователям
                    account.status = AccountStatus.RATE_LIMITED
                    
                    return InviteResult(
                        status=InviteResultStatus.PEER_FLOOD,
                        error_message="Слишком много запросов к пользователям",
                        error_code="peer_flood",
                        retry_after=datetime.utcnow() + timedelta(hours=24),
                        execution_time=execution_time,
                        account_id=account.account_id,
                        can_retry=False  // PeerFlood обычно на долго
                    )
            
            // Общий rate limiting
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
            // Privacy restrictions
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
            // Bad request - различные ошибки
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
        
        // Общая ошибка
        return InviteResult(
            status=InviteResultStatus.FAILED,
            error_message=f"Ошибка Integration Service: {error_data.get('detail', str(error))}",
            error_code=f"http_{error.response.status_code}",
            execution_time=execution_time,
            account_id=account.account_id,
            can_retry=error.response.status_code >= 500  // Ретрай только для server errors
        )
    
    def _calculate_retry_time(self, account: PlatformAccount) -> datetime:
        """Вычисление времени для повторной попытки"""
        
        if account.flood_wait_until:
            return account.flood_wait_until
        
        // Если достигнут дневной лимит - ждем до следующего дня
        if account.daily_invites_used >= account.daily_invite_limit:
            tomorrow = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            return tomorrow
        
        // Если достигнут часовой лимит - ждем до следующего часа
        if account.hourly_invites_used >= account.hourly_invite_limit:
            next_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            return next_hour
        
        // По умолчанию - через час
        return datetime.utcnow() + timedelta(hours=1) 