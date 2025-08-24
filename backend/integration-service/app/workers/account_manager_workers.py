"""
Account Manager Background Workers
Фоновые задачи для автоматического восстановления и обслуживания аккаунтов
"""
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
from celery import Celery
from celery.schedules import crontab
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..core.database import get_async_session
from ..services.account_manager import AccountManagerService
from ..services.flood_ban_manager import FloodBanManager
from ..services.rate_limiting_service import RateLimitingService
from ..services.integration_log_service import IntegrationLogService

logger = logging.getLogger(__name__)

# Celery app configuration
settings = get_settings()

celery_app = Celery(
    "account_manager_workers",
    broker=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB + 4}",
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB + 4}",
    include=["app.workers.account_manager_workers"]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    task_routes={
        "account_manager_workers.process_account_recoveries": {"queue": "account_manager_high"},
        "account_manager_workers.reset_daily_limits": {"queue": "account_manager_high"},
        "account_manager_workers.monitor_account_health": {"queue": "account_manager_normal"},
        "account_manager_workers.cleanup_expired_locks": {"queue": "account_manager_low"},
        "account_manager_workers.cleanup_rate_limit_data": {"queue": "account_manager_low"},
        "account_manager_workers.generate_health_report": {"queue": "account_manager_low"}
    }
)

# Periodic tasks schedule
celery_app.conf.beat_schedule = {
    # Восстановление аккаунтов каждые 5 минут
    "process-account-recoveries": {
        "task": "account_manager_workers.process_account_recoveries",
        "schedule": 300.0,  # 5 минут
        "options": {"queue": "account_manager_high"}
    },
    
    # Сброс дневных лимитов в полночь UTC
    "reset-daily-limits": {
        "task": "account_manager_workers.reset_daily_limits",
        "schedule": crontab(hour=0, minute=0),
        "options": {"queue": "account_manager_high"}
    },
    
    # Мониторинг здоровья аккаунтов каждые 15 минут
    "monitor-account-health": {
        "task": "account_manager_workers.monitor_account_health",
        "schedule": 900.0,  # 15 минут
        "options": {"queue": "account_manager_normal"}
    },
    
    # Очистка устаревших блокировок каждые 30 минут
    "cleanup-expired-locks": {
        "task": "account_manager_workers.cleanup_expired_locks",
        "schedule": 1800.0,  # 30 минут
        "options": {"queue": "account_manager_low"}
    },
    
    # Очистка данных rate limiting каждый час
    "cleanup-rate-limit-data": {
        "task": "account_manager_workers.cleanup_rate_limit_data",
        "schedule": 3600.0,  # 1 час
        "options": {"queue": "account_manager_low"}
    },
    
    # Генерация отчета о здоровье каждые 6 часов
    "generate-health-report": {
        "task": "account_manager_workers.generate_health_report",
        "schedule": 21600.0,  # 6 часов
        "options": {"queue": "account_manager_low"}
    }
}

# Helper function для async операций в Celery
async def run_async_task(coro):
    """Запустить async операцию в Celery таске"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return await coro
    finally:
        loop.close()

# Background tasks
@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 60})
def process_account_recoveries(self, limit: int = 50):
    """
    Обработать ожидающие восстановления аккаунтов
    """
    async def _process_recoveries():
        try:
            logger.info("🔄 Starting account recovery processing")
            
            # Получаем database session
            async with get_async_session() as session:
                flood_ban_manager = FloodBanManager()
                log_service = IntegrationLogService()
                
                # Обрабатываем восстановления
                processed_count = await flood_ban_manager.process_pending_recoveries(
                    session=session,
                    limit=limit
                )
                
                # Логируем результат
                await log_service.log_integration_action(
                    session=session,
                    user_id=0,  # Системная операция
                    integration_type="telegram",
                    action="background_recovery_processing",
                    status="success",
                    details={
                        "processed_count": processed_count,
                        "limit": limit,
                        "task_id": str(self.request.id)
                    }
                )
                
                logger.info(f"✅ Processed {processed_count} account recoveries")
                return {"processed_count": processed_count, "success": True}
                
        except Exception as e:
            logger.error(f"❌ Error processing account recoveries: {e}")
            raise
    
    return asyncio.run(_process_recoveries())

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 60})
def reset_daily_limits(self):
    """
    Сбросить дневные лимиты для всех аккаунтов
    """
    async def _reset_limits():
        try:
            logger.info("🔄 Starting daily limits reset")
            
            async with get_async_session() as session:
                flood_ban_manager = FloodBanManager()
                log_service = IntegrationLogService()
                
                # Сбрасываем лимиты
                affected_count = await flood_ban_manager.reset_daily_limits(session)
                
                # Логируем результат
                await log_service.log_integration_action(
                    session=session,
                    user_id=0,  # Системная операция
                    integration_type="telegram",
                    action="background_daily_limits_reset",
                    status="success",
                    details={
                        "affected_count": affected_count,
                        "reset_date": datetime.utcnow().isoformat(),
                        "task_id": str(self.request.id)
                    }
                )
                
                logger.info(f"✅ Reset daily limits for {affected_count} accounts")
                return {"affected_count": affected_count, "success": True}
                
        except Exception as e:
            logger.error(f"❌ Error resetting daily limits: {e}")
            raise
    
    return asyncio.run(_reset_limits())

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 60})
def monitor_account_health(self, check_limit: int = 100):
    """
    Мониторинг здоровья аккаунтов и автоматическое планирование восстановления
    """
    async def _monitor_health():
        try:
            logger.info("🔄 Starting account health monitoring")
            
            async with get_async_session() as session:
                from ..models.telegram_sessions import TelegramSession
                from sqlalchemy import select, and_
                
                flood_ban_manager = FloodBanManager()
                log_service = IntegrationLogService()
                
                # Получаем аккаунты с потенциальными проблемами
                now = datetime.utcnow()
                result = await session.execute(
                    select(TelegramSession)
                    .where(
                        and_(
                            TelegramSession.is_active == True,
                            or_(
                                TelegramSession.flood_wait_until.isnot(None),
                                TelegramSession.blocked_until.isnot(None),
                                TelegramSession.error_count > 3
                            )
                        )
                    )
                    .limit(check_limit)
                )
                
                problematic_accounts = result.scalars().all()
                
                health_issues = []
                scheduled_recoveries = 0
                
                for account in problematic_accounts:
                    # Проверяем здоровье аккаунта
                    health_status = await flood_ban_manager.check_account_health(
                        session=session,
                        account_id=account.id
                    )
                    
                    if not health_status.is_healthy and health_status.recovery_eta:
                        # Планируем восстановление если еще не запланировано
                        recovery_scheduled = await flood_ban_manager.schedule_account_recovery(
                            session=session,
                            account_id=account.id,
                            recovery_time=health_status.recovery_eta,
                            recovery_type="auto_monitoring"
                        )
                        
                        if recovery_scheduled:
                            scheduled_recoveries += 1
                    
                    if not health_status.is_healthy:
                        health_issues.append({
                            "account_id": str(account.id),
                            "phone": account.phone,
                            "issues": health_status.issues,
                            "recovery_eta": health_status.recovery_eta.isoformat() if health_status.recovery_eta else None
                        })
                
                # Логируем результат мониторинга
                await log_service.log_integration_action(
                    session=session,
                    user_id=0,  # Системная операция
                    integration_type="telegram",
                    action="background_health_monitoring",
                    status="success",
                    details={
                        "checked_accounts": len(problematic_accounts),
                        "health_issues_found": len(health_issues),
                        "scheduled_recoveries": scheduled_recoveries,
                        "task_id": str(self.request.id)
                    }
                )
                
                logger.info(f"✅ Health monitoring: {len(problematic_accounts)} accounts checked, {scheduled_recoveries} recoveries scheduled")
                return {
                    "checked_accounts": len(problematic_accounts),
                    "health_issues": health_issues,
                    "scheduled_recoveries": scheduled_recoveries,
                    "success": True
                }
                
        except Exception as e:
            logger.error(f"❌ Error monitoring account health: {e}")
            raise
    
    return asyncio.run(_monitor_health())

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 60})
def cleanup_expired_locks(self):
    """
    Очистить устаревшие блокировки аккаунтов
    """
    async def _cleanup_locks():
        try:
            logger.info("🔄 Starting expired locks cleanup")
            
            async with get_async_session() as session:
                from ..models.telegram_sessions import TelegramSession
                from sqlalchemy import update, and_
                
                log_service = IntegrationLogService()
                
                # Очищаем истекшие блокировки в базе данных
                now = datetime.utcnow()
                result = await session.execute(
                    update(TelegramSession)
                    .where(
                        and_(
                            TelegramSession.locked == True,
                            TelegramSession.locked_until < now
                        )
                    )
                    .values(
                        locked=False,
                        locked_by=None,
                        locked_until=None
                    )
                )
                
                cleared_locks = result.rowcount
                await session.commit()
                
                # Очищаем Redis locks
                account_manager = AccountManagerService()
                redis_keys = account_manager.redis_client.keys("account_lock:*")
                expired_redis_locks = 0
                
                for key in redis_keys:
                    ttl = account_manager.redis_client.ttl(key)
                    if ttl == -1:  # Ключ без TTL (не должно быть)
                        account_manager.redis_client.delete(key)
                        expired_redis_locks += 1
                
                # Логируем результат
                await log_service.log_integration_action(
                    session=session,
                    user_id=0,  # Системная операция
                    integration_type="telegram",
                    action="background_locks_cleanup",
                    status="success",
                    details={
                        "cleared_db_locks": cleared_locks,
                        "cleared_redis_locks": expired_redis_locks,
                        "task_id": str(self.request.id)
                    }
                )
                
                logger.info(f"✅ Cleaned up {cleared_locks} DB locks and {expired_redis_locks} Redis locks")
                return {
                    "cleared_db_locks": cleared_locks,
                    "cleared_redis_locks": expired_redis_locks,
                    "success": True
                }
                
        except Exception as e:
            logger.error(f"❌ Error cleaning up expired locks: {e}")
            raise
    
    return asyncio.run(_cleanup_locks())

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 60})
def cleanup_rate_limit_data(self):
    """
    Очистить устаревшие данные rate limiting
    """
    async def _cleanup_rate_limits():
        try:
            logger.info("🔄 Starting rate limit data cleanup")
            
            rate_limiting_service = RateLimitingService()
            
            # Очищаем устаревшие данные
            deleted_count = await rate_limiting_service.cleanup_expired_data()
            
            # Логируем результат
            async with get_async_session() as session:
                log_service = IntegrationLogService()
                
                await log_service.log_integration_action(
                    session=session,
                    user_id=0,  # Системная операция
                    integration_type="telegram",
                    action="background_rate_limit_cleanup",
                    status="success",
                    details={
                        "deleted_keys": deleted_count,
                        "task_id": str(self.request.id)
                    }
                )
            
            logger.info(f"✅ Cleaned up {deleted_count} rate limit keys")
            return {"deleted_keys": deleted_count, "success": True}
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up rate limit data: {e}")
            raise
    
    return asyncio.run(_cleanup_rate_limits())

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 60})
def generate_health_report(self):
    """
    Генерировать отчет о состоянии Account Manager системы
    """
    async def _generate_report():
        try:
            logger.info("🔄 Generating Account Manager health report")
            
            async with get_async_session() as session:
                flood_ban_manager = FloodBanManager()
                log_service = IntegrationLogService()
                
                # Собираем статистику восстановления
                recovery_stats = await flood_ban_manager.get_account_recovery_stats(session)
                
                # Собираем общую статистику аккаунтов
                from ..models.telegram_sessions import TelegramSession
                from sqlalchemy import select, func, and_
                
                now = datetime.utcnow()
                
                # Общее количество аккаунтов
                total_result = await session.execute(
                    select(func.count(TelegramSession.id))
                    .where(TelegramSession.is_active == True)
                )
                total_accounts = total_result.scalar() or 0
                
                # Заблокированные аккаунты
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
                locked_accounts = locked_result.scalar() or 0
                
                # Аккаунты с высоким использованием лимитов
                high_usage_result = await session.execute(
                    select(func.count(TelegramSession.id))
                    .where(
                        and_(
                            TelegramSession.is_active == True,
                            or_(
                                TelegramSession.used_invites_today >= 25,  # >80% от 30
                                TelegramSession.used_messages_today >= 25   # >80% от 30
                            )
                        )
                    )
                )
                high_usage_accounts = high_usage_result.scalar() or 0
                
                # Формируем отчет
                health_report = {
                    "generated_at": datetime.utcnow().isoformat(),
                    "task_id": str(self.request.id),
                    "summary": {
                        "total_accounts": total_accounts,
                        "healthy_accounts": recovery_stats.get("healthy_accounts", 0),
                        "locked_accounts": locked_accounts,
                        "high_usage_accounts": high_usage_accounts,
                        "health_percentage": (recovery_stats.get("healthy_accounts", 0) / total_accounts * 100) if total_accounts > 0 else 0
                    },
                    "recovery_stats": recovery_stats,
                    "alerts": []
                }
                
                # Добавляем алерты при проблемах
                if recovery_stats.get("flood_wait_active", 0) > total_accounts * 0.1:  # >10% в flood wait
                    health_report["alerts"].append({
                        "level": "warning",
                        "message": f"High number of accounts in flood wait: {recovery_stats.get('flood_wait_active', 0)}"
                    })
                
                if recovery_stats.get("blocked_active", 0) > total_accounts * 0.05:  # >5% заблокированы
                    health_report["alerts"].append({
                        "level": "critical",
                        "message": f"High number of blocked accounts: {recovery_stats.get('blocked_active', 0)}"
                    })
                
                if high_usage_accounts > total_accounts * 0.3:  # >30% с высоким использованием
                    health_report["alerts"].append({
                        "level": "info",
                        "message": f"High number of accounts with high usage: {high_usage_accounts}"
                    })
                
                # Логируем отчет
                await log_service.log_integration_action(
                    session=session,
                    user_id=0,  # Системная операция
                    integration_type="telegram",
                    action="background_health_report",
                    status="success",
                    details=health_report
                )
                
                logger.info(f"✅ Generated health report: {health_report['summary']['health_percentage']:.1f}% healthy accounts")
                return health_report
                
        except Exception as e:
            logger.error(f"❌ Error generating health report: {e}")
            raise
    
    return asyncio.run(_generate_report())

# Manual task triggers (для вызова через API или администрирование)
@celery_app.task(bind=True)
def force_account_recovery(self, account_id: str):
    """
    Принудительно восстановить конкретный аккаунт
    """
    async def _force_recovery():
        try:
            from uuid import UUID
            account_uuid = UUID(account_id)
            
            async with get_async_session() as session:
                flood_ban_manager = FloodBanManager()
                
                # Пытаемся восстановить аккаунт
                success = await flood_ban_manager._recover_account(
                    session=session,
                    account_id=account_uuid,
                    recovery_type="manual_force"
                )
                
                logger.info(f"✅ Force recovery for account {account_id}: {'success' if success else 'failed'}")
                return {"account_id": account_id, "success": success}
                
        except Exception as e:
            logger.error(f"❌ Error in force recovery for account {account_id}: {e}")
            raise
    
    return asyncio.run(_force_recovery())

@celery_app.task(bind=True)
def emergency_unlock_account(self, account_id: str, service_name: str = "emergency"):
    """
    Экстренно разблокировать аккаунт
    """
    async def _emergency_unlock():
        try:
            from uuid import UUID
            account_uuid = UUID(account_id)
            
            async with get_async_session() as session:
                account_manager = AccountManagerService()
                
                # Освобождаем Redis lock
                await account_manager._release_account_lock(account_uuid, service_name)
                
                # Обновляем в базе данных
                from ..models.telegram_sessions import TelegramSession
                from sqlalchemy import update
                
                await session.execute(
                    update(TelegramSession)
                    .where(TelegramSession.id == account_uuid)
                    .values(
                        locked=False,
                        locked_by=None,
                        locked_until=None
                    )
                )
                await session.commit()
                
                logger.info(f"✅ Emergency unlock for account {account_id}")
                return {"account_id": account_id, "unlocked": True}
                
        except Exception as e:
            logger.error(f"❌ Error in emergency unlock for account {account_id}: {e}")
            raise
    
    return asyncio.run(_emergency_unlock())

# Main entry point для запуска worker'а
if __name__ == "__main__":
    celery_app.start()