"""
Flood/Ban Management Service
Автоматическое управление флуд-ожиданиями, банами и восстановлением аккаунтов
"""
import logging
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_, func
import redis
import json

from ..models.telegram_sessions import TelegramSession
from ..models.account_manager_types import (
    AccountStatus, ErrorType, FloodWaitInfo, AccountHealthStatus
)
from ..core.config import get_settings
from .integration_log_service import IntegrationLogService

logger = logging.getLogger(__name__)

class FloodBanManager:
    """Управление флуд-ожиданиями и банами аккаунтов"""
    
    def __init__(self):
        self.settings = get_settings()
        self.log_service = IntegrationLogService()
        
        # Redis для хранения состояний и очередей восстановления
        self.redis_client = redis.Redis(
            host=self.settings.REDIS_HOST,
            port=self.settings.REDIS_PORT,
            db=self.settings.REDIS_DB + 2,  # Отдельная DB для Flood/Ban Manager
            decode_responses=True
        )
    
    async def check_account_health(
        self,
        session: AsyncSession,
        account_id: UUID
    ) -> AccountHealthStatus:
        """
        Проверить состояние здоровья аккаунта
        
        Args:
            session: Database session
            account_id: ID аккаунта
        
        Returns:
            AccountHealthStatus: Подробная информация о состоянии аккаунта
        """
        try:
            # Получить аккаунт
            result = await session.execute(
                select(TelegramSession).where(TelegramSession.id == account_id)
            )
            account = result.scalar_one_or_none()
            
            if not account:
                return AccountHealthStatus(
                    account_id=account_id,
                    is_healthy=False,
                    status=AccountStatus.DISABLED,
                    issues=["Account not found"],
                    recovery_eta=None,
                    last_check=datetime.utcnow()
                )
            
            now = datetime.utcnow()
            issues = []
            is_healthy = True
            recovery_eta = None
            
            # Проверка статуса
            if account.status != AccountStatus.ACTIVE:
                is_healthy = False
                issues.append(f"Account status: {account.status}")
            
            # Проверка flood wait
            if account.flood_wait_until and account.flood_wait_until > now:
                is_healthy = False
                issues.append(f"Flood wait until: {account.flood_wait_until}")
                if not recovery_eta or account.flood_wait_until < recovery_eta:
                    recovery_eta = account.flood_wait_until
            
            # Проверка блокировки
            if account.blocked_until and account.blocked_until > now:
                is_healthy = False
                issues.append(f"Blocked until: {account.blocked_until}")
                if not recovery_eta or account.blocked_until < recovery_eta:
                    recovery_eta = account.blocked_until
            
            # Проверка лимитов
            if account.used_invites_today >= account.daily_invite_limit:
                is_healthy = False
                issues.append("Daily invite limit reached")
            
            if account.used_messages_today >= account.daily_message_limit:
                is_healthy = False
                issues.append("Daily message limit reached")
            
            # Проверка ошибок
            if account.error_count > 5:
                is_healthy = False
                issues.append(f"High error count: {account.error_count}")
            
            # Проверка блокировки другим сервисом
            if account.locked and account.locked_until and account.locked_until > now:
                is_healthy = False
                issues.append(f"Locked by: {account.locked_by} until: {account.locked_until}")
                if not recovery_eta or account.locked_until < recovery_eta:
                    recovery_eta = account.locked_until
            
            return AccountHealthStatus(
                account_id=account_id,
                is_healthy=is_healthy,
                status=account.status,
                issues=issues if issues else ["Account is healthy"],
                recovery_eta=recovery_eta,
                last_check=now,
                metadata={
                    "used_invites_today": account.used_invites_today,
                    "used_messages_today": account.used_messages_today,
                    "error_count": account.error_count,
                    "last_used_at": account.last_used_at.isoformat() if account.last_used_at else None
                }
            )
            
        except Exception as e:
            logger.error(f"❌ Error checking account health {account_id}: {e}")
            return AccountHealthStatus(
                account_id=account_id,
                is_healthy=False,
                status=AccountStatus.DISABLED,
                issues=[f"Health check error: {str(e)}"],
                recovery_eta=None,
                last_check=datetime.utcnow()
            )
    
    async def schedule_account_recovery(
        self,
        session: AsyncSession,
        account_id: UUID,
        recovery_time: datetime,
        recovery_type: str = "auto"
    ) -> bool:
        """
        Запланировать восстановление аккаунта
        
        Args:
            session: Database session
            account_id: ID аккаунта
            recovery_time: Время восстановления
            recovery_type: Тип восстановления (auto, manual, flood_wait, ban_lift)
        
        Returns:
            bool: Успешность планирования
        """
        try:
            logger.info(f"📅 Scheduling recovery for account {account_id} at {recovery_time}")
            
            # Сохраняем в Redis с timestamp как score для sorted set
            recovery_timestamp = recovery_time.timestamp()
            recovery_data = {
                "account_id": str(account_id),
                "recovery_time": recovery_time.isoformat(),
                "recovery_type": recovery_type,
                "scheduled_at": datetime.utcnow().isoformat()
            }
            
            # Добавляем в sorted set для автоматической обработки по времени
            self.redis_client.zadd(
                "account_recovery_queue",
                {json.dumps(recovery_data): recovery_timestamp}
            )
            
            # Также сохраняем детали восстановления
            recovery_key = f"recovery:{account_id}"
            self.redis_client.setex(
                recovery_key,
                int((recovery_time - datetime.utcnow()).total_seconds()) + 3600,  # +1 час буфер
                json.dumps(recovery_data)
            )
            
            # Логируем операцию
            await self.log_service.log_integration_action(
                session=session,
                user_id=0,  # Системная операция
                integration_type="telegram",
                action="recovery_scheduled",
                status="success",
                details={
                    "account_id": str(account_id),
                    "recovery_time": recovery_time.isoformat(),
                    "recovery_type": recovery_type
                }
            )
            
            logger.info(f"✅ Recovery scheduled for account {account_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error scheduling recovery for account {account_id}: {e}")
            return False
    
    async def process_pending_recoveries(
        self,
        session: AsyncSession,
        limit: int = 50
    ) -> int:
        """
        Обработать ожидающие восстановления
        
        Args:
            session: Database session
            limit: Максимальное количество восстановлений за раз
        
        Returns:
            int: Количество обработанных восстановлений
        """
        try:
            now = datetime.utcnow()
            current_timestamp = now.timestamp()
            
            # Получаем восстановления, время которых пришло
            recoveries = self.redis_client.zrangebyscore(
                "account_recovery_queue",
                0,
                current_timestamp,
                start=0,
                num=limit,
                withscores=True
            )
            
            processed_count = 0
            
            for recovery_json, score in recoveries:
                try:
                    recovery_data = json.loads(recovery_json)
                    account_id = UUID(recovery_data["account_id"])
                    recovery_type = recovery_data["recovery_type"]
                    
                    # Пытаемся восстановить аккаунт
                    success = await self._recover_account(session, account_id, recovery_type)
                    
                    if success:
                        processed_count += 1
                        logger.info(f"✅ Account {account_id} recovered successfully")
                    else:
                        logger.warning(f"⚠️ Failed to recover account {account_id}")
                    
                    # Удаляем из очереди независимо от результата
                    self.redis_client.zrem("account_recovery_queue", recovery_json)
                    
                    # Удаляем детали восстановления
                    recovery_key = f"recovery:{account_id}"
                    self.redis_client.delete(recovery_key)
                    
                except Exception as e:
                    logger.error(f"❌ Error processing recovery: {e}")
                    # Удаляем некорректную запись
                    self.redis_client.zrem("account_recovery_queue", recovery_json)
            
            if processed_count > 0:
                logger.info(f"📈 Processed {processed_count} account recoveries")
            
            return processed_count
            
        except Exception as e:
            logger.error(f"❌ Error processing pending recoveries: {e}")
            return 0
    
    async def _recover_account(
        self,
        session: AsyncSession,
        account_id: UUID,
        recovery_type: str
    ) -> bool:
        """
        Восстановить конкретный аккаунт
        
        Args:
            session: Database session
            account_id: ID аккаунта
            recovery_type: Тип восстановления
        
        Returns:
            bool: Успешность восстановления
        """
        try:
            # Получаем аккаунт
            result = await session.execute(
                select(TelegramSession).where(TelegramSession.id == account_id)
            )
            account = result.scalar_one_or_none()
            
            if not account:
                logger.warning(f"❌ Account {account_id} not found for recovery")
                return False
            
            now = datetime.utcnow()
            update_values = {}
            
            # Очищаем flood wait если время прошло
            if account.flood_wait_until and account.flood_wait_until <= now:
                update_values['flood_wait_until'] = None
                logger.info(f"🔓 Cleared flood wait for account {account_id}")
            
            # Очищаем блокировку если время прошло
            if account.blocked_until and account.blocked_until <= now:
                update_values['blocked_until'] = None
                logger.info(f"🔓 Cleared block for account {account_id}")
            
            # Переводим в активное состояние если можем
            if account.status in [AccountStatus.FLOOD_WAIT, AccountStatus.BLOCKED]:
                # Проверяем, что все таймеры истекли
                if (not account.flood_wait_until or account.flood_wait_until <= now) and \
                   (not account.blocked_until or account.blocked_until <= now):
                    update_values['status'] = AccountStatus.ACTIVE
                    logger.info(f"✅ Restored account {account_id} to ACTIVE status")
            
            # Сбрасываем счетчик ошибок при успешном восстановлении
            if recovery_type == "auto" and update_values:
                update_values['error_count'] = 0
            
            # Применяем обновления если есть
            if update_values:
                await session.execute(
                    update(TelegramSession)
                    .where(TelegramSession.id == account_id)
                    .values(**update_values)
                )
                await session.commit()
                
                # Логируем восстановление
                await self.log_service.log_integration_action(
                    session=session,
                    user_id=account.user_id,
                    integration_type="telegram",
                    action="account_recovered",
                    status="success",
                    details={
                        "account_id": str(account_id),
                        "recovery_type": recovery_type,
                        "updates": list(update_values.keys())
                    }
                )
                
                return True
            else:
                logger.info(f"ℹ️ Account {account_id} doesn't need recovery")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error recovering account {account_id}: {e}")
            return False
    
    async def reset_daily_limits(
        self,
        session: AsyncSession,
        target_date: datetime = None
    ) -> int:
        """
        Сбросить дневные лимиты для всех аккаунтов
        
        Args:
            session: Database session
            target_date: Дата для сброса (по умолчанию сегодня)
        
        Returns:
            int: Количество обновленных аккаунтов
        """
        try:
            target_date = target_date or datetime.utcnow()
            logger.info(f"🔄 Resetting daily limits for date: {target_date.date()}")
            
            # Сбрасываем лимиты для всех активных аккаунтов
            result = await session.execute(
                update(TelegramSession)
                .where(TelegramSession.is_active == True)
                .values(
                    used_invites_today=0,
                    used_messages_today=0,
                    contacts_today=0,
                    per_channel_invites={},
                    last_limit_reset=target_date
                )
            )
            
            affected_rows = result.rowcount
            await session.commit()
            
            # Логируем операцию
            await self.log_service.log_integration_action(
                session=session,
                user_id=0,  # Системная операция
                integration_type="telegram",
                action="daily_limits_reset",
                status="success",
                details={
                    "reset_date": target_date.isoformat(),
                    "affected_accounts": affected_rows
                }
            )
            
            logger.info(f"✅ Reset daily limits for {affected_rows} accounts")
            return affected_rows
            
        except Exception as e:
            logger.error(f"❌ Error resetting daily limits: {e}")
            return 0
    
    async def get_flood_wait_info(
        self,
        session: AsyncSession,
        account_id: UUID
    ) -> Optional[FloodWaitInfo]:
        """
        Получить информацию о флуд-ожидании аккаунта
        
        Args:
            session: Database session
            account_id: ID аккаунта
        
        Returns:
            FloodWaitInfo или None
        """
        try:
            result = await session.execute(
                select(TelegramSession).where(TelegramSession.id == account_id)
            )
            account = result.scalar_one_or_none()
            
            if not account or not account.flood_wait_until:
                return None
            
            now = datetime.utcnow()
            
            if account.flood_wait_until <= now:
                return None  # Flood wait истек
            
            return FloodWaitInfo(
                account_id=account_id,
                wait_until=account.flood_wait_until,
                seconds_remaining=int((account.flood_wait_until - now).total_seconds()),
                reason="Telegram API flood protection",
                can_retry_at=account.flood_wait_until
            )
            
        except Exception as e:
            logger.error(f"❌ Error getting flood wait info for account {account_id}: {e}")
            return None
    
    async def get_account_recovery_stats(self, session: AsyncSession) -> Dict[str, int]:
        """
        Получить статистику восстановления аккаунтов
        
        Args:
            session: Database session
        
        Returns:
            Dict с статистикой
        """
        try:
            now = datetime.utcnow()
            
            # Статистика по статусам аккаунтов
            result = await session.execute(
                select(
                    TelegramSession.status,
                    func.count(TelegramSession.id).label('count')
                )
                .where(TelegramSession.is_active == True)
                .group_by(TelegramSession.status)
            )
            status_stats = {row.status: row.count for row in result}
            
            # Аккаунты в flood wait
            flood_wait_result = await session.execute(
                select(func.count(TelegramSession.id))
                .where(
                    and_(
                        TelegramSession.is_active == True,
                        TelegramSession.flood_wait_until > now
                    )
                )
            )
            flood_wait_count = flood_wait_result.scalar() or 0
            
            # Заблокированные аккаунты
            blocked_result = await session.execute(
                select(func.count(TelegramSession.id))
                .where(
                    and_(
                        TelegramSession.is_active == True,
                        TelegramSession.blocked_until > now
                    )
                )
            )
            blocked_count = blocked_result.scalar() or 0
            
            # Аккаунты с высоким количеством ошибок
            high_error_result = await session.execute(
                select(func.count(TelegramSession.id))
                .where(
                    and_(
                        TelegramSession.is_active == True,
                        TelegramSession.error_count > 5
                    )
                )
            )
            high_error_count = high_error_result.scalar() or 0
            
            # Заблокированные другими сервисами
            locked_result = await session.execute(
                select(func.count(TelegramSession.id))
                .where(
                    and_(
                        TelegramSession.is_active == True,
                        TelegramSession.locked == True,
                        TelegramSession.locked_until > now
                    )
                )
            )
            locked_count = locked_result.scalar() or 0
            
            # Очередь восстановления
            recovery_queue_size = self.redis_client.zcard("account_recovery_queue") or 0
            
            return {
                "total_active": sum(status_stats.values()),
                "status_breakdown": status_stats,
                "flood_wait_active": flood_wait_count,
                "blocked_active": blocked_count,
                "high_error_count": high_error_count,
                "locked_by_services": locked_count,
                "recovery_queue_size": recovery_queue_size,
                "healthy_accounts": status_stats.get(AccountStatus.ACTIVE, 0) - flood_wait_count - blocked_count - locked_count
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting recovery stats: {e}")
            return {
                "total_active": 0,
                "status_breakdown": {},
                "flood_wait_active": 0,
                "blocked_active": 0,
                "high_error_count": 0,
                "locked_by_services": 0,
                "recovery_queue_size": 0,
                "healthy_accounts": 0
            }