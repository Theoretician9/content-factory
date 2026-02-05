"""
Account Manager Service
Централизованное управление Telegram аккаунтами для всех сервисов проекта
"""
import logging
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_, func
from sqlalchemy.orm import selectinload
import redis
import json
import re

from ..models.telegram_sessions import TelegramSession
from ..models.account_manager_types import (
    AccountStatus, ActionType, AccountPurpose, ErrorType,
    AccountLimits, AccountUsageStats, TelegramAccountAllocation,
    AccountErrorResult, FloodWaitInfo, AccountHealthStatus
)
from ..core.config import get_settings
from .integration_log_service import IntegrationLogService

logger = logging.getLogger(__name__)

class AccountManagerService:
    """Централизованное управление Telegram аккаунтами"""
    
    def __init__(self):
        self.settings = get_settings()
        self.log_service = IntegrationLogService()
        
        # Redis для distributed locks
        self.redis_client = redis.Redis(
            host=self.settings.REDIS_HOST,
            port=self.settings.REDIS_PORT,
            db=self.settings.REDIS_DB + 1,  # Отдельная DB для Account Manager
            decode_responses=True
        )
        
        self.default_limits = AccountLimits()
        
        # Timeout для блокировки аккаунтов (минуты)
        self.default_lock_timeout = 30
    
    async def allocate_account(
        self,
        session: AsyncSession,
        user_id: int,
        purpose: AccountPurpose,
        service_name: str = "unknown",
        preferred_account_id: Optional[UUID] = None,
        timeout_minutes: int = None,
        target_channel_id: Optional[str] = None
    ) -> Optional[TelegramAccountAllocation]:
        """
        Выделить аккаунт для использования сервисом
        
        Args:
            session: Database session
            user_id: ID пользователя
            purpose: Цель использования аккаунта
            service_name: Имя сервиса, запрашивающего аккаунт
            preferred_account_id: Предпочтительный аккаунт (если есть)
            timeout_minutes: Таймаут блокировки в минутах
            target_channel_id: ID целевого канала (если есть)
        """
        try:
            logger.info(f"🔍 Allocating account for user {user_id}, purpose: {purpose}, service: {service_name}")
            
            timeout_minutes = timeout_minutes or self.default_lock_timeout
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=timeout_minutes)
            
            # Нормализуем идентификатор канала: slug без t.me/ и @, в нижнем регистре
            norm_channel = None
            if target_channel_id:
                try:
                    raw = str(target_channel_id).strip()
                    if raw.startswith('https://t.me/') or raw.startswith('http://t.me/') or raw.startswith('t.me/'):
                        raw = raw.split('/')[-1]
                    if raw.startswith('@'):
                        raw = raw[1:]
                    norm_channel = raw.lower()
                except Exception:
                    norm_channel = target_channel_id

            # 1. Найти доступные аккаунты
            available_accounts = await self._find_available_accounts(
                session=session,
                user_id=user_id,
                purpose=purpose,
                service_name=service_name,
                preferred_account_id=preferred_account_id,
                target_channel_id=norm_channel
            )
            
            if not available_accounts:
                logger.warning(f"❌ No available accounts for user {user_id}, purpose: {purpose}")
                return None
            
            # 2. Выбрать оптимальный аккаунт
            selected_account = await self._select_optimal_account(available_accounts, purpose)
            
            # 3. Заблокировать аккаунт с distributed lock
            lock_acquired = await self._acquire_account_lock(
                selected_account.id, service_name, timeout_minutes
            )
            
            if not lock_acquired:
                logger.warning(f"❌ Failed to acquire lock for account {selected_account.id}")
                return None
            
            # 4. НЕ обновляем поля locked в базе данных - только Redis locks!
            # Обновляем только информацию о последнем использовании
            await session.execute(
                update(TelegramSession)
                .where(TelegramSession.id == selected_account.id)
                .values(
                    last_used_at=datetime.now(timezone.utc)
                )
            )
            await session.commit()
            
            # 5. Создать allocation объект
            allocation = TelegramAccountAllocation(
                account_id=selected_account.id,
                user_id=selected_account.user_id,
                phone=selected_account.phone,
                session_data=selected_account.session_data,
                allocated_at=datetime.now(timezone.utc),
                allocated_by=service_name,
                purpose=purpose,
                expires_at=expires_at,
                limits=self.default_limits,
                current_usage={
                    'invites_today': selected_account.used_invites_today,
                    'messages_today': selected_account.used_messages_today,
                    'contacts_today': selected_account.contacts_today
                }
            )
            
            # 6. Логировать операцию
            await self.log_service.log_integration_action(
                session=session,
                user_id=user_id,
                integration_type="telegram",
                action="account_allocated",
                status="success",
                details={
                    "account_id": str(selected_account.id),
                    "phone": selected_account.phone,
                    "purpose": purpose,
                    "service": service_name,
                    "expires_at": expires_at.isoformat()
                }
            )
            
            logger.info(f"✅ Account {selected_account.id} allocated to {service_name} for {timeout_minutes} minutes")
            return allocation
            
        except Exception as e:
            logger.error(f"❌ Error allocating account: {e}")
            # В случае ошибки, освободить lock если был установлен
            if 'selected_account' in locals():
                await self._release_account_lock(selected_account.id, service_name)
            raise
    
    async def release_account(
        self,
        session: AsyncSession,
        account_id: UUID,
        service_name: str,
        usage_stats: AccountUsageStats
    ) -> bool:
        """
        Освободить аккаунт после использования
        
        Args:
            session: Database session
            account_id: ID аккаунта
            service_name: Имя сервиса
            usage_stats: Статистика использования
        
        Returns:
            bool: Успешность операции
        """
        try:
            logger.info(f"🔓 Releasing account {account_id} from {service_name}")
            
            # 1. Получить текущий аккаунт
            result = await session.execute(
                select(TelegramSession).where(TelegramSession.id == account_id)
            )
            account = result.scalar_one_or_none()
            
            if not account:
                logger.error(f"❌ Account {account_id} not found")
                return False
            
            # 2. Обновить статистику использования (НЕ трогаем locked поля!)
            new_values = {
                'last_used_at': datetime.now(timezone.utc)
            }
            
            # Обновляем счетчики использования
            if usage_stats.invites_sent > 0:
                new_values['used_invites_today'] = account.used_invites_today + usage_stats.invites_sent
            
            if usage_stats.messages_sent > 0:
                new_values['used_messages_today'] = account.used_messages_today + usage_stats.messages_sent
            
            if usage_stats.contacts_added > 0:
                new_values['contacts_today'] = account.contacts_today + usage_stats.contacts_added
            
            # Обновляем per-channel статистику
            if usage_stats.channels_used:
                current_per_channel = account.per_channel_invites or {}
                for channel_id in usage_stats.channels_used:
                    if channel_id not in current_per_channel:
                        current_per_channel[channel_id] = {'today': 0, 'total': 0}
                    
                    current_per_channel[channel_id]['today'] += usage_stats.invites_sent
                    current_per_channel[channel_id]['total'] += usage_stats.invites_sent
                
                new_values['per_channel_invites'] = current_per_channel
            
            # 3. Если была ошибка, обработать ее
            if not usage_stats.success and usage_stats.error_type:
                error_result = await self.handle_account_error(
                    session, account_id, usage_stats.error_type, 
                    usage_stats.error_message or "Unknown error",
                    {'service': service_name}
                )
                
                # Обновить статус на основе обработки ошибки
                if error_result:
                    new_values['status'] = error_result.new_status
                    if error_result.recovery_time:
                        if error_result.error_type == ErrorType.FLOOD_WAIT:
                            new_values['flood_wait_until'] = error_result.recovery_time
                        elif error_result.error_type in [ErrorType.PEER_FLOOD, ErrorType.PHONE_NUMBER_BANNED]:
                            new_values['blocked_until'] = error_result.recovery_time
            
            # 4. Применить обновления
            await session.execute(
                update(TelegramSession)
                .where(TelegramSession.id == account_id)
                .values(**new_values)
            )
            await session.commit()
            
            # 5. Освободить distributed lock
            await self._release_account_lock(account_id, service_name)
            
            # 6. Логировать операцию
            await self.log_service.log_integration_action(
                session=session,
                user_id=account.user_id,
                integration_type="telegram",
                action="account_released",
                status="success",
                details={
                    "account_id": str(account_id),
                    "service": service_name,
                    "usage_stats": {
                        "invites_sent": usage_stats.invites_sent,
                        "messages_sent": usage_stats.messages_sent,
                        "contacts_added": usage_stats.contacts_added,
                        "success": usage_stats.success,
                        "error_type": usage_stats.error_type
                    }
                }
            )
            
            logger.info(f"✅ Account {account_id} released successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error releasing account {account_id}: {e}")
            return False
    
    async def handle_account_error(
        self,
        session: AsyncSession,
        account_id: UUID,
        error_type: ErrorType,
        error_message: str,
        context: Dict[str, Any] = None
    ) -> Optional[AccountErrorResult]:
        """
        Обработать ошибку аккаунта
        
        Args:
            session: Database session
            account_id: ID аккаунта
            error_type: Тип ошибки
            error_message: Сообщение об ошибке
            context: Дополнительный контекст
        
        Returns:
            AccountErrorResult с информацией о принятых мерах
        """
        try:
            logger.warning(f"⚠️ Handling account error: {error_type} for account {account_id}")
            
            context = context or {}
            now = datetime.now(timezone.utc)
            
            # Определяем действия на основе типа ошибки
            if error_type == ErrorType.FLOOD_WAIT:
                # Извлекаем количество секунд из сообщения
                match = re.search(r'(\d+)', error_message)
                seconds = int(match.group(1)) if match else 300  # Fallback: 5 минут
                
                recovery_time = now + timedelta(seconds=seconds + 60)  # +1 минута буфер
                new_status = AccountStatus.FLOOD_WAIT
                action_taken = f"Set flood wait until {recovery_time}"
                should_retry = True
                
            elif error_type == ErrorType.PEER_FLOOD:
                recovery_time = now + timedelta(hours=24)  # 24 часа
                new_status = AccountStatus.BLOCKED
                action_taken = "Blocked for 24 hours due to peer flood"
                should_retry = False
                
            elif error_type in [ErrorType.PHONE_NUMBER_BANNED, ErrorType.USER_DEACTIVATED]:
                recovery_time = None  # Permanent
                new_status = AccountStatus.DISABLED
                action_taken = "Permanently disabled"
                should_retry = False
                
            elif error_type == ErrorType.AUTH_KEY_ERROR:
                recovery_time = None
                new_status = AccountStatus.DISABLED
                action_taken = "Disabled due to auth key error"
                should_retry = False
                
            else:
                # Неизвестная ошибка - увеличиваем счетчик ошибок
                recovery_time = now + timedelta(minutes=30)
                new_status = AccountStatus.ACTIVE  # Оставляем активным
                action_taken = "Incremented error count"
                should_retry = True
            
            # Обновляем аккаунт в базе данных
            update_values = {
                'status': new_status,
                'error_count': TelegramSession.error_count + 1
            }
            
            if error_type == ErrorType.FLOOD_WAIT and recovery_time:
                update_values['flood_wait_until'] = recovery_time
            elif error_type in [ErrorType.PEER_FLOOD, ErrorType.PHONE_NUMBER_BANNED] and recovery_time:
                update_values['blocked_until'] = recovery_time
            
            await session.execute(
                update(TelegramSession)
                .where(TelegramSession.id == account_id)
                .values(**update_values)
            )
            await session.commit()
            
            # Создаем результат
            result = AccountErrorResult(
                account_id=account_id,
                error_type=error_type,
                action_taken=action_taken,
                new_status=new_status,
                recovery_time=recovery_time,
                should_retry=should_retry,
                message=f"Error handled: {error_message}"
            )
            
            # Логируем операцию
            await self.log_service.log_integration_action(
                session=session,
                user_id=context.get('user_id', 0),
                integration_type="telegram",
                action="account_error_handled",
                status="success",
                details={
                    "account_id": str(account_id),
                    "error_type": error_type,
                    "error_message": error_message,
                    "action_taken": action_taken,
                    "new_status": new_status,
                    "recovery_time": recovery_time.isoformat() if recovery_time else None,
                    "context": context
                }
            )
            
            logger.info(f"✅ Error handled for account {account_id}: {action_taken}")
            return result
        except Exception as e:
            logger.error(f"❌ Error handling account error: {e}")
            return None
    
    async def _find_available_accounts(
        self,
        session: AsyncSession,
        user_id: int,
        purpose: AccountPurpose,
        service_name: Optional[str] = None,
        preferred_account_id: Optional[UUID] = None,
        target_channel_id: Optional[str] = None
    ) -> List[TelegramSession]:
        """
        Найти доступные аккаунты для пользователя
        """
        now = datetime.now(timezone.utc)
        
        logger.info(f"🔍 ДИАГНОСТИКА: Поиск аккаунтов для user_id={user_id}, purpose={purpose}")
        logger.info(f"🔍 ДИАГНОСТИКА: Текущее время (UTC): {now}")
        
        # Bypass: если указан preferred_account_id, попробуем вернуть ровно этот аккаунт
        # (если принадлежит пользователю, активен). Если залочен в Redis — разрешаем только если lock наш (тот же сервис).
        if preferred_account_id:
            lock_key_pref = f"account_lock:{preferred_account_id}"
            lock_exists = self.redis_client.exists(lock_key_pref)
            lock_ours = False
            if lock_exists and service_name:
                current_val = self.redis_client.get(lock_key_pref) or ""
                lock_ours = current_val.startswith(f"{service_name}:")
                if lock_ours:
                    logger.info(f"✅ ДИАГНОСТИКА: Preferred аккаунт залочен нами ({service_name}), разрешаем переиспользование")
            if not lock_exists or lock_ours:
                result_pref = await session.execute(
                    select(TelegramSession).where(
                        and_(
                            TelegramSession.id == preferred_account_id,
                            TelegramSession.user_id == user_id,
                            TelegramSession.is_active == True,
                        )
                    )
                )
                preferred_acc = result_pref.scalar_one_or_none()
                if preferred_acc is not None:
                    logger.info(f"✅ ДИАГНОСТИКА: Возвращаем preferred аккаунт: {preferred_acc.id}")
                    return [preferred_acc]
            if lock_exists and not lock_ours:
                logger.debug(f"🔒 Preferred account {preferred_account_id} is locked by another service, bypass пропущен")

        # Базовые условия для доступности аккаунта (НЕ проверяем locked поля в БД!)
        # Логика статусов:
        # - ACTIVE: всегда допустим, если нет актуального flood_wait_until/blocked_until.
        # - FLOOD_WAIT: допустим ТОЛЬКО если flood_wait_until отсутствует или уже в прошлом
        #   (аккаунт «вышел из флуда», даже если статус ещё не обновлён).
        # - BLOCKED: допустим ТОЛЬКО если blocked_until отсутствует или уже в прошлом
        #   (временная блокировка закончилась).
        # - DISABLED: никогда не берём.
        conditions = [
            TelegramSession.user_id == user_id,
            TelegramSession.is_active == True,
            or_(
                TelegramSession.status == AccountStatus.ACTIVE.value,
                and_(
                    TelegramSession.status == AccountStatus.FLOOD_WAIT.value,
                    or_(
                        TelegramSession.flood_wait_until.is_(None),
                        TelegramSession.flood_wait_until <= now
                    )
                ),
                and_(
                    TelegramSession.status == AccountStatus.BLOCKED.value,
                    or_(
                        TelegramSession.blocked_until.is_(None),
                        TelegramSession.blocked_until <= now
                    )
                )
            ),
            or_(
                TelegramSession.flood_wait_until.is_(None),
                TelegramSession.flood_wait_until <= now
            ),
            or_(
                TelegramSession.blocked_until.is_(None),
                TelegramSession.blocked_until <= now
            )
        ]

        # Если указан предпочтительный аккаунт (и bypass не сработал) — ограничим выбор именно им
        if preferred_account_id:
            conditions.append(TelegramSession.id == preferred_account_id)

        query = select(TelegramSession).where(and_(*conditions))
        
        # Сортировка по приоритету (меньше всего использован)
        query = query.order_by(
            TelegramSession.used_invites_today.asc(),
            TelegramSession.used_messages_today.asc(),
            TelegramSession.last_used_at.asc().nulls_first()
        )
        
        result = await session.execute(query)
        accounts = result.scalars().all()
        
        logger.info(f"🔍 ДИАГНОСТИКА: Найдено {len(accounts)} аккаунтов после SQL фильтрации")
        
        # Дополнительная фильтрация по лимитам в зависимости от цели (игнорируем DB-флаг locked, т.к. используем Redis locks)
        filtered_accounts = []
        for i, account in enumerate(accounts):
            logger.info(f"🔍 ДИАГНОСТИКА: Аккаунт {i+1}: id={account.id}, status='{account.status}', is_active={account.is_active}")
            logger.info(f"🔍 ДИАГНОСТИКА: flood_wait_until={account.flood_wait_until}, blocked_until={account.blocked_until}")

            # 🔄 ЛЕНИВОЕ ВОССТАНОВЛЕНИЕ СТАТУСА:
            # Если статус FLOOD_WAIT/BLOCKED, но время уже прошло — сразу обновляем запись в БД,
            # чтобы Account Manager всегда видел актуальный статус.
            try:
                status_val = str(getattr(account, "status", AccountStatus.ACTIVE.value) or AccountStatus.ACTIVE.value)
                flood_until = getattr(account, "flood_wait_until", None)
                blocked_until = getattr(account, "blocked_until", None)
                need_update = False
                update_values = {}

                if status_val == AccountStatus.FLOOD_WAIT.value:
                    if not flood_until or (isinstance(flood_until, datetime) and flood_until <= now):
                        update_values["status"] = AccountStatus.ACTIVE.value
                        update_values["flood_wait_until"] = None
                        need_update = True

                if status_val == AccountStatus.BLOCKED.value and blocked_until and isinstance(blocked_until, datetime):
                    if blocked_until <= now:
                        update_values["status"] = AccountStatus.ACTIVE.value
                        update_values["blocked_until"] = None
                        need_update = True

                if need_update:
                    await session.execute(
                        update(TelegramSession)
                        .where(TelegramSession.id == account.id)
                        .values(**update_values)
                    )
                    await session.commit()
                    for k, v in update_values.items():
                        setattr(account, k, v)
                    logger.info(
                        f"🔄 AccountManager: Нормализован статус аккаунта {account.id} в БД: {update_values}"
                    )
            except Exception as norm_err:
                logger.warning(f"⚠️ AccountManager: Ошибка нормализации статуса аккаунта {account.id}: {norm_err}")
            
            # ПРОВЕРЯЕМ REDIS LOCKS - главное отличие от старой логики!
            lock_key = f"account_lock:{account.id}"
            redis_locked = self.redis_client.exists(lock_key)
            logger.info(f"🔍 ДИАГНОСТИКА: Redis lock для {account.id}: {redis_locked}")
            
            if redis_locked:
                # Тот же сервис может переиспользовать свой lock (обновим TTL при allocate)
                lock_ours = False
                if service_name:
                    current_val = self.redis_client.get(lock_key) or ""
                    lock_ours = current_val.startswith(f"{service_name}:")
                if not lock_ours:
                    logger.debug(f"🔒 Account {account.id} is locked in Redis, skipping")
                    continue
                logger.debug(f"🔒 Account {account.id} locked by us ({service_name}), allowing")
            
            # Базовая доступность (без учета поля locked в БД)
            base_ok = (
                bool(account.is_active)
                and str(account.status) == 'active'
                and (not account.flood_wait_until or account.flood_wait_until <= now)
                and (not account.blocked_until or account.blocked_until <= now)
            )
            if not base_ok:
                logger.debug(f"⛔ Account {account.id} not base-available for purpose {purpose}")
                continue

            if purpose == AccountPurpose.INVITE_CAMPAIGN:
                # Ленивый сброс дневных счётчиков: если reset_at в прошлом (Celery не сбросил в полночь),
                # сбрасываем счётчики в БД и считаем лимиты нулевыми для этого аккаунта
                reset_at_val = getattr(account, 'reset_at', None)
                if reset_at_val is not None and reset_at_val.tzinfo is None:
                    reset_at_val = reset_at_val.replace(tzinfo=timezone.utc)
                counters_stale = reset_at_val is not None and now > reset_at_val
                if counters_stale:
                    next_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                    await session.execute(
                        update(TelegramSession)
                        .where(TelegramSession.id == account.id)
                        .values(
                            used_invites_today=0,
                            used_messages_today=0,
                            contacts_today=0,
                            per_channel_invites={},
                            reset_at=next_midnight
                        )
                    )
                    await session.flush()
                    logger.info(f"🔄 Lazy reset daily limits for account {account.id} (reset_at was in the past)")
                used_today = 0 if counters_stale else getattr(account, 'used_invites_today', 0)
                daily_limit = getattr(account, 'daily_invite_limit', 30)
                per_ch = (account.per_channel_invites or {}).get(target_channel_id or "", {'today': 0, 'total': 0})
                ch_today = 0 if counters_stale else per_ch.get('today', 0)
                ch_total = 0 if counters_stale else per_ch.get('total', 0)
                per_ch_limit = getattr(account, 'per_channel_invite_limit', 15)
                ch_total_limit = getattr(account, 'max_per_channel_total', 200)
                logger.info(
                    f"🔍 ДИАГНОСТИКА INVITE_CAMPAIGN: account={account.id} used_invites_today={used_today} "
                    f"daily_limit={daily_limit} target_channel_id={target_channel_id!r} "
                    f"per_channel today={ch_today} total={ch_total} limits({per_ch_limit}/{ch_total_limit})"
                )
                # Дневной лимит аккаунта
                if used_today >= daily_limit:
                    logger.info(f"⛔ ДИАГНОСТИКА: Аккаунт {account.id} отфильтрован для INVITE_CAMPAIGN: дневной лимит ({used_today} >= {daily_limit})")
                    continue
                # Лимиты по каналу
                if target_channel_id:
                    if ch_today >= per_ch_limit:
                        logger.info(f"⛔ ДИАГНОСТИКА: Аккаунт {account.id} отфильтрован для INVITE_CAMPAIGN: лимит по каналу сегодня ({ch_today} >= {per_ch_limit}) для {target_channel_id}")
                        continue
                    if ch_total >= ch_total_limit:
                        logger.info(f"⛔ ДИАГНОСТИКА: Аккаунт {account.id} отфильтрован для INVITE_CAMPAIGN: лимит по каналу всего ({ch_total} >= {ch_total_limit}) для {target_channel_id}")
                        continue
                filtered_accounts.append(account)
                logger.info(f"✅ ДИАГНОСТИКА: Аккаунт {account.id} подходит для INVITE_CAMPAIGN")
            elif purpose == AccountPurpose.MESSAGE_CAMPAIGN and account.can_send_message():
                filtered_accounts.append(account)
                logger.info(f"✅ ДИАГНОСТИКА: Аккаунт {account.id} подходит для MESSAGE_CAMPAIGN")
            elif purpose in [AccountPurpose.PARSING, AccountPurpose.GENERAL]:
                filtered_accounts.append(account)
                logger.info(f"✅ ДИАГНОСТИКА: Аккаунт {account.id} подходит для {purpose}")
            else:
                logger.warning(f"❌ ДИАГНОСТИКА: Аккаунт {account.id} НЕ подходит для {purpose}")
        
        logger.info(f"🔍 ДИАГНОСТИКА: Итого отфильтровано {len(filtered_accounts)} доступных аккаунтов")
        return filtered_accounts
    
    async def _select_optimal_account(
        self,
        accounts: List[TelegramSession],
        purpose: AccountPurpose
    ) -> TelegramSession:
        """
        Выбрать оптимальный аккаунт из доступных
        """
        if not accounts:
            raise ValueError("No accounts provided")
        
        # Сортировка по критериям оптимальности
        def account_score(account: TelegramSession) -> float:
            score = 0.0
            
            # Чем меньше использован, тем лучше
            if purpose == AccountPurpose.INVITE_CAMPAIGN:
                usage_ratio = account.used_invites_today / account.daily_invite_limit
            elif purpose == AccountPurpose.MESSAGE_CAMPAIGN:
                usage_ratio = account.used_messages_today / account.daily_message_limit
            else:
                usage_ratio = (account.used_invites_today + account.used_messages_today) / 60
            
            score += (1.0 - usage_ratio) * 100
            
            # Бонус за отсутствие недавних ошибок
            if account.error_count == 0:
                score += 10
            
            # Бонус за давность использования
            if account.last_used_at:
                hours_since_use = (datetime.now(timezone.utc) - account.last_used_at).total_seconds() / 3600
                score += min(hours_since_use, 24)  # Максимум 24 часа
            else:
                score += 24  # Никогда не использовался
            
            return score
        
        # Выбираем аккаунт с наивысшим score
        optimal_account = max(accounts, key=account_score)
        return optimal_account
    
    async def _acquire_account_lock(
        self,
        account_id: UUID,
        service_name: str,
        timeout_minutes: int
    ) -> bool:
        """
        Получить distributed lock на аккаунт.
        Если lock уже принадлежит тому же сервису — перезаписываем (обновляем TTL).
        """
        lock_key = f"account_lock:{account_id}"
        lock_value = f"{service_name}:{datetime.now(timezone.utc).isoformat()}"
        ttl_seconds = timeout_minutes * 60
        
        current_value = self.redis_client.get(lock_key)
        if current_value and current_value.startswith(f"{service_name}:"):
            # Наш старый lock — перезаписываем и обновляем TTL
            self.redis_client.setex(lock_key, ttl_seconds, lock_value)
            logger.debug(f"🔒 Re-acquired (refreshed) lock for account {account_id} by {service_name}")
            return True
        
        # Устанавливаем lock с TTL только если ключ не существует
        result = self.redis_client.set(
            lock_key,
            lock_value,
            nx=True,
            ex=ttl_seconds
        )
        if result:
            logger.debug(f"🔒 Acquired lock for account {account_id} by {service_name}")
            return True
        logger.warning(f"❌ Failed to acquire lock for account {account_id}, already locked")
        return False
    
    async def _release_account_lock(
        self,
        account_id: UUID,
        service_name: str
    ) -> bool:
        """
        Освободить distributed lock на аккаунт
        """
        lock_key = f"account_lock:{account_id}"
        
        # Получаем текущее значение lock
        current_value = self.redis_client.get(lock_key)
        
        if current_value and current_value.startswith(f"{service_name}:"):
            # Удаляем lock только если он принадлежит нашему сервису
            self.redis_client.delete(lock_key)
            logger.debug(f"🔓 Released lock for account {account_id} by {service_name}")
            return True
        elif current_value:
            logger.warning(f"❌ Cannot release lock for account {account_id}, owned by: {current_value}")
            return False
        else:
            # Lock уже не существует
            return True
            # коммент для гита