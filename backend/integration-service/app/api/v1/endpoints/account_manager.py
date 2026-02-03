"""
Account Manager API Endpoints
API для управления аккаунтами через Account Manager
"""
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from ....database import get_async_session
from ....models.account_manager_types import (
    AccountPurpose, ActionType, ErrorType, TelegramAccountAllocation,
    AccountUsageStats, AccountHealthStatus, FloodWaitInfo
)
from ....services.account_manager import AccountManagerService
from ....services.flood_ban_manager import FloodBanManager
from ....services.rate_limiting_service import RateLimitingService
from ....models.telegram_sessions import TelegramSession

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Account Manager"])

# Pydantic schemas
class AccountAllocationRequest(BaseModel):
    """Запрос на выделение аккаунта"""
    user_id: int = Field(..., description="ID пользователя")
    purpose: AccountPurpose = Field(..., description="Цель использования аккаунта")
    service_name: str = Field(..., description="Имя сервиса-заказчика")
    preferred_account_id: Optional[UUID] = Field(None, description="Предпочтительный аккаунт")
    timeout_minutes: Optional[int] = Field(30, description="Таймаут блокировки в минутах")
    target_channel_id: Optional[str] = Field(None, description="ID целевого канала/паблика для кампании")

class AccountReleaseRequest(BaseModel):
    """Запрос на освобождение аккаунта"""
    service_name: str = Field(..., description="Имя сервиса")
    usage_stats: Dict[str, Any] = Field(..., description="Статистика использования")
    
    def to_usage_stats(self) -> AccountUsageStats:
        """Конвертировать в AccountUsageStats"""
        return AccountUsageStats(
            invites_sent=self.usage_stats.get('invites_sent', 0),
            messages_sent=self.usage_stats.get('messages_sent', 0),
            contacts_added=self.usage_stats.get('contacts_added', 0),
            success=self.usage_stats.get('success', True),
            error_type=self.usage_stats.get('error_type'),
            error_message=self.usage_stats.get('error_message'),
            channels_used=self.usage_stats.get('channels_used', [])
        )

class AccountErrorRequest(BaseModel):
    """Запрос на обработку ошибки аккаунта"""
    error_type: ErrorType = Field(..., description="Тип ошибки")
    error_message: str = Field(..., description="Сообщение об ошибке")
    context: Optional[Dict[str, Any]] = Field(None, description="Дополнительный контекст")

class RateLimitCheckRequest(BaseModel):
    """Запрос на проверку rate limit"""
    action_type: ActionType = Field(..., description="Тип действия")
    target_channel_id: Optional[str] = Field(None, description="ID целевого канала")
    allow_locked: Optional[bool] = Field(False, description="Не считать lock причиной недоступности (вызов после allocate)")

class RateLimitRecordRequest(BaseModel):
    """Запрос на запись выполненного действия"""
    action_type: ActionType = Field(..., description="Тип действия")
    target_channel_id: Optional[str] = Field(None, description="ID целевого канала")
    success: bool = Field(True, description="Успешность действия")

class ReleaseAllRequest(BaseModel):
    """Запрос на освобождение всех аккаунтов сервиса"""
    service_name: str = Field(..., description="Имя сервиса")
    force: bool = Field(False, description="Принудительное освобождение")

class AccountsSummaryResponse(BaseModel):
    success: bool
    user_id: int
    purpose: Optional[AccountPurpose] = None
    total_accounts: int
    active_accounts: int
    available_now: int
    aggregates: Dict[str, Any]
    accounts: List[Dict[str, Any]]

# Dependency injection
async def get_account_manager() -> AccountManagerService:
    return AccountManagerService()

async def get_flood_ban_manager() -> FloodBanManager:
    return FloodBanManager()

async def get_rate_limiting_service() -> RateLimitingService:
    return RateLimitingService()

# Endpoints
@router.post("/allocate", response_model=Dict[str, Any])
async def allocate_account(
    request: AccountAllocationRequest,
    session: AsyncSession = Depends(get_async_session),
    account_manager: AccountManagerService = Depends(get_account_manager)
):
    """
    Выделить аккаунт для использования сервисом
    """
    try:
        logger.info(f"🔍 Account allocation request from {request.service_name} for user {request.user_id}")
        
        allocation = await account_manager.allocate_account(
            session=session,
            user_id=request.user_id,
            purpose=request.purpose,
            service_name=request.service_name,
            preferred_account_id=request.preferred_account_id,
            timeout_minutes=request.timeout_minutes,
            target_channel_id=request.target_channel_id
        )
        
        if not allocation:
            raise HTTPException(
                status_code=404,
                detail="No available accounts found for the specified criteria"
            )
        
        return {
            "success": True,
            "allocation": {
                "account_id": str(allocation.account_id),
                "user_id": allocation.user_id,
                "phone": allocation.phone,
                "session_data": allocation.session_data,  # Добавляем session_data для parsing service
                "allocated_at": allocation.allocated_at.isoformat(),
                "allocated_by": allocation.allocated_by,
                "purpose": allocation.purpose,
                "expires_at": allocation.expires_at.isoformat(),
                "limits": {
                    "daily_invite_limit": allocation.limits.daily_invite_limit,
                    "daily_message_limit": allocation.limits.daily_message_limit,
                    "contacts_daily_limit": allocation.limits.contacts_daily_limit,
                    "per_channel_invite_limit": allocation.limits.per_channel_invite_limit
                },
                "current_usage": allocation.current_usage
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error allocating account: {e}")
        raise HTTPException(status_code=500, detail=f"Error allocating account: {str(e)}")

@router.post("/release/{account_id}")
async def release_account(
    account_id: UUID,
    request: AccountReleaseRequest,
    session: AsyncSession = Depends(get_async_session),
    account_manager: AccountManagerService = Depends(get_account_manager)
):
    """
    Освободить аккаунт после использования
    """
    try:
        logger.info(f"🔓 Account release request for {account_id} from {request.service_name}")
        
        usage_stats = request.to_usage_stats()
        
        success = await account_manager.release_account(
            session=session,
            account_id=account_id,
            service_name=request.service_name,
            usage_stats=usage_stats
        )
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to release account"
            )
        
        return {
            "success": True,
            "message": f"Account {account_id} released successfully",
            "released_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error releasing account {account_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error releasing account: {str(e)}")

@router.post("/handle-error/{account_id}")
async def handle_account_error(
    account_id: UUID,
    request: AccountErrorRequest,
    session: AsyncSession = Depends(get_async_session),
    account_manager: AccountManagerService = Depends(get_account_manager)
):
    """
    Обработать ошибку аккаунта
    """
    try:
        logger.info(f"⚠️ Account error handling for {account_id}: {request.error_type}")
        
        result = await account_manager.handle_account_error(
            session=session,
            account_id=account_id,
            error_type=request.error_type,
            error_message=request.error_message,
            context=request.context or {}
        )
        
        if not result:
            raise HTTPException(
                status_code=400,
                detail="Failed to handle account error"
            )
        
        return {
            "success": True,
            "result": {
                "account_id": str(result.account_id),
                "error_type": result.error_type,
                "action_taken": result.action_taken,
                "new_status": result.new_status,
                "recovery_time": result.recovery_time.isoformat() if result.recovery_time else None,
                "should_retry": result.should_retry,
                "message": result.message
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error handling account error for {account_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error handling account error: {str(e)}")

@router.get("/accounts/summary", response_model=Dict[str, Any])
async def get_accounts_summary(
    user_id: int = Query(..., description="ID пользователя"),
    purpose: Optional[AccountPurpose] = Query(None, description="Цель использования аккаунтов"),
    target_channel_id: Optional[str] = Query(None, description="ID целевого канала/паблика для проверки per-channel лимитов"),
    status: Optional[str] = Query(None, description="Фильтр по статусу (active, flood_wait, blocked, cooling_down, ...)"),
    only_available: bool = Query(False, description="Фильтровать только доступные сейчас аккаунты"),
    include_unavailable: bool = Query(False, description="Включить ВСЕ аккаунты пользователя (игнорировать доступность)"),
    sort_by: Optional[str] = Query(None, description="Сортировка: last_used_at|used_invites_today|error_count"),
    limit: int = Query(500, ge=1, le=2000, description="Максимум аккаунтов в ответе"),
    session: AsyncSession = Depends(get_async_session),
    account_manager: AccountManagerService = Depends(get_account_manager),
    rate_limiting: RateLimitingService = Depends(get_rate_limiting_service)
):
    """
    Получить список доступных аккаунтов пользователя
    """
    try:
        # Нормализация идентификатора канала: поддержка t.me/<slug> и @slug
        if target_channel_id:
            try:
                raw = str(target_channel_id).strip()
                if raw.startswith('https://t.me/') or raw.startswith('http://t.me/') or raw.startswith('t.me/'):
                    raw = raw.split('/')[-1]
                if raw.startswith('@'):
                    raw = raw[1:]
                target_channel_id = raw.lower()
            except Exception:
                pass
        # Либо возвращаем все аккаунты пользователя (минимальные фильтры), либо только доступные сейчас
        if include_unavailable:
            q = select(TelegramSession).where(
                TelegramSession.user_id == user_id,
                TelegramSession.is_active == True,
            )
            result_all = await session.execute(q)
            available_accounts = result_all.scalars().all()
        else:
            # Используем приватный метод через объект (не идеально, но для API нужно)
            available_accounts = await account_manager._find_available_accounts(
                session=session,
                user_id=user_id,
                purpose=purpose or AccountPurpose.GENERAL
            )
        
        # Применяем фильтры по статусу и доступности
        filtered = []
        for acc in available_accounts:
            st = str(acc.status)
            if status and st != status:
                continue
            if only_available and not getattr(acc, "is_available", False):
                continue
            filtered.append(acc)

        # Сортировка
        if sort_by == "last_used_at":
            filtered.sort(key=lambda a: (getattr(a, "last_used_at", None) or datetime.min))
        elif sort_by == "used_invites_today":
            filtered.sort(key=lambda a: (getattr(a, "used_invites_today", 0)))
        elif sort_by == "error_count":
            filtered.sort(key=lambda a: (getattr(a, "error_count", 0)), reverse=True)

        # Обрезаем список по limit
        candidates = filtered[:limit]
        
        # Подсчитываем агрегаты
        can_invite_true = 0
        capacity_today_sum = 0
        capacity_today_by_channel = 0
        status_distribution = {}
        active_accounts = 0
        available_now = 0
        
        for acc in candidates:
            # Проверяем, можно ли приглашать в целевой канал
            if target_channel_id:
                try:
                    allowed, details = await rate_limiting.check_rate_limit(
                        session=session,
                        account_id=acc.id,
                        action_type=ActionType.INVITE,
                        target_channel_id=target_channel_id
                    )
                    can_invite_in_channel = bool(allowed)
                    if can_invite_in_channel:
                        can_invite_true += 1
                    # Пытаемся извлечь остатки по лимитам из details, если сервис их отдаёт
                    if isinstance(details, dict):
                        remaining_in_channel = details.get("remaining_today_in_channel")
                        if isinstance(remaining_in_channel, int):
                            capacity_today_by_channel += max(0, remaining_in_channel)
                except Exception as rl_err:
                    logger.warning(f"Rate limit check failed for {acc.id}: {rl_err}")
                    can_invite_in_channel = False

            # Общая дневная емкость по аккаунту (если доступна)
            # Ожидается, что AccountManagerService или rate limiting хранит used_invites_today и дневной лимит аккаунта (например, 30)
            try:
                daily_limit_account = getattr(acc, "daily_invite_limit", None) or 30
                used_today = getattr(acc, "used_invites_today", 0)
                capacity_today_sum += max(0, int(daily_limit_account) - int(used_today))
            except Exception:
                pass
            
            # Статусы аккаунтов
            st = str(acc.status)
            if st not in status_distribution:
                status_distribution[st] = 0
            status_distribution[st] += 1
            
            # Активные и доступные аккаунты
            if getattr(acc, "is_active", False):
                active_accounts += 1
            if getattr(acc, "is_available", False):
                available_now += 1
        
        accounts_data = []
        for account in candidates:
            accounts_data.append({
                "account_id": str(account.id),
                "phone": account.phone,
                "status": account.status,
                "is_available": account.is_available,
                "used_invites_today": account.used_invites_today,
                "used_messages_today": account.used_messages_today,
                "contacts_today": account.contacts_today,
                "error_count": account.error_count,
                "last_used_at": account.last_used_at.isoformat() if account.last_used_at else None,
                "flood_wait_until": account.flood_wait_until.isoformat() if account.flood_wait_until else None,
                "blocked_until": account.blocked_until.isoformat() if account.blocked_until else None
            })
        
        response = {
            "success": True,
            "user_id": user_id,
            "purpose": (purpose or AccountPurpose.GENERAL),
            "total_accounts": len(accounts_data),
            "active_accounts": active_accounts,
            "available_now": available_now,
            "aggregates": {
                "status_distribution": status_distribution,
                "can_invite_in_channel_true": can_invite_true if target_channel_id else None,
                "capacity_today_sum": capacity_today_sum,
                "capacity_today_by_channel": capacity_today_by_channel if target_channel_id else None
            },
            "accounts": accounts_data
        }
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Error getting available accounts for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting available accounts: {str(e)}")

@router.get("/health/{account_id}")
async def check_account_health(
    account_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    flood_ban_manager: FloodBanManager = Depends(get_flood_ban_manager)
):
    """
    Проверить состояние здоровья аккаунта
    """
    try:
        health_status = await flood_ban_manager.check_account_health(
            session=session,
            account_id=account_id
        )
        
        return {
            "success": True,
            "health": {
                "account_id": str(health_status.account_id),
                "is_healthy": health_status.is_healthy,
                "status": health_status.status,
                "issues": health_status.issues,
                "recovery_eta": health_status.recovery_eta.isoformat() if health_status.recovery_eta else None,
                "last_check": health_status.last_check.isoformat(),
                "metadata": health_status.metadata
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error checking account health for {account_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error checking account health: {str(e)}")

@router.get("/flood-wait/{account_id}")
async def get_flood_wait_info(
    account_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    flood_ban_manager: FloodBanManager = Depends(get_flood_ban_manager)
):
    """
    Получить информацию о флуд-ожидании аккаунта
    """
    try:
        flood_info = await flood_ban_manager.get_flood_wait_info(
            session=session,
            account_id=account_id
        )
        
        if not flood_info:
            return {
                "success": True,
                "flood_wait_active": False,
                "message": "No active flood wait for this account"
            }
        
        return {
            "success": True,
            "flood_wait_active": True,
            "flood_wait": {
                "account_id": str(flood_info.account_id),
                "wait_until": flood_info.wait_until.isoformat(),
                "seconds_remaining": flood_info.seconds_remaining,
                "reason": flood_info.reason,
                "can_retry_at": flood_info.can_retry_at.isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting flood wait info for {account_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting flood wait info: {str(e)}")

@router.post("/schedule-recovery/{account_id}")
async def schedule_account_recovery(
    account_id: UUID,
    recovery_time: datetime,
    recovery_type: str = "manual",
    session: AsyncSession = Depends(get_async_session),
    flood_ban_manager: FloodBanManager = Depends(get_flood_ban_manager)
):
    """
    Запланировать восстановление аккаунта
    """
    try:
        success = await flood_ban_manager.schedule_account_recovery(
            session=session,
            account_id=account_id,
            recovery_time=recovery_time,
            recovery_type=recovery_type
        )
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to schedule account recovery"
            )
        
        return {
            "success": True,
            "message": f"Recovery scheduled for account {account_id}",
            "recovery_time": recovery_time.isoformat(),
            "recovery_type": recovery_type
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error scheduling recovery for {account_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error scheduling recovery: {str(e)}")

@router.post("/rate-limit/check/{account_id}")
async def check_rate_limit(
    account_id: UUID,
    request: RateLimitCheckRequest,
    session: AsyncSession = Depends(get_async_session),
    rate_limiting: RateLimitingService = Depends(get_rate_limiting_service)
):
    """
    Проверить можно ли выполнить действие с учетом лимитов
    """
    try:
        allowed, details = await rate_limiting.check_rate_limit(
            session=session,
            account_id=account_id,
            action_type=request.action_type,
            target_channel_id=request.target_channel_id,
            allow_locked=request.allow_locked or False
        )
        
        return {
            "success": True,
            "allowed": allowed,
            "reason": details.get("error") if isinstance(details, dict) else None,
            "details": details
        }
        
    except Exception as e:
        logger.error(f"❌ Error checking rate limit for {account_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error checking rate limit: {str(e)}")

@router.post("/rate-limit/record/{account_id}")
async def record_action(
    account_id: UUID,
    request: RateLimitRecordRequest,
    session: AsyncSession = Depends(get_async_session),
    rate_limiting: RateLimitingService = Depends(get_rate_limiting_service)
):
    """
    Записать выполненное действие и обновить лимиты
    """
    try:
        success = await rate_limiting.record_action(
            session=session,
            account_id=account_id,
            action_type=request.action_type,
            target_channel_id=request.target_channel_id,
            success=request.success
        )
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to record action"
            )
        
        return {
            "success": True,
            "message": "Action recorded successfully",
            "recorded_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error recording action for {account_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error recording action: {str(e)}")

@router.get("/rate-limit/status/{account_id}")
async def get_rate_limit_status(
    account_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    rate_limiting: RateLimitingService = Depends(get_rate_limiting_service)
):
    """
    Получить текущий статус лимитов аккаунта
    """
    try:
        status = await rate_limiting.get_account_limits_status(
            session=session,
            account_id=account_id
        )
        
        return {
            "success": True,
            "status": status
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting rate limit status for {account_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting rate limit status: {str(e)}")

@router.get("/status")
async def get_account_manager_status(
    session: AsyncSession = Depends(get_async_session),
    account_manager: AccountManagerService = Depends(get_account_manager)
):
    """
    Получить общий статус Account Manager и статистику аккаунтов
    """
    try:
        # Получаем статистику Redis locks
        lock_pattern = f"account_lock:*"
        all_locks = account_manager.redis_client.keys(lock_pattern)
        
        locked_accounts = {}
        total_locked = 0
        
        for lock_key in all_locks:
            lock_value = account_manager.redis_client.get(lock_key)
            if lock_value:
                service_name = lock_value.split(':')[0] if ':' in lock_value else 'unknown'
                if service_name not in locked_accounts:
                    locked_accounts[service_name] = 0
                locked_accounts[service_name] += 1
                total_locked += 1
        
        # Получаем общее количество аккаунтов из базы данных
        try:
            from ....models.telegram_account import TelegramAccount
            from sqlalchemy import select, func
            
            total_accounts_result = await session.execute(select(func.count(TelegramAccount.id)))
            total_accounts = total_accounts_result.scalar() or 0
            
            active_accounts_result = await session.execute(
                select(func.count(TelegramAccount.id)).where(TelegramAccount.is_active == True)
            )
            active_accounts = active_accounts_result.scalar() or 0
            
        except Exception as db_error:
            logger.warning(f"⚠️ Could not get account counts from database: {db_error}")
            total_accounts = "unknown"
            active_accounts = "unknown"
        
        return {
            "success": True,
            "status": "operational",
            "total_accounts": total_accounts,
            "active_accounts": active_accounts,
            "locked_accounts": total_locked,
            "available_accounts": active_accounts - total_locked if isinstance(active_accounts, int) and isinstance(total_locked, int) else "unknown",
            "locked_by_service": locked_accounts,
            "redis_connected": True,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting Account Manager status: {e}")
        return {
            "success": False,
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@router.get("/stats/recovery")
async def get_recovery_stats(
    session: AsyncSession = Depends(get_async_session),
    flood_ban_manager: FloodBanManager = Depends(get_flood_ban_manager)
):
    """
    Получить статистику восстановления аккаунтов
    """
    try:
        stats = await flood_ban_manager.get_account_recovery_stats(session)
        
        return {
            "success": True,
            "stats": stats,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting recovery stats: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting recovery stats: {str(e)}")

@router.post("/release-all")
async def release_all_accounts(
    request: ReleaseAllRequest,
    session: AsyncSession = Depends(get_async_session),
    account_manager: AccountManagerService = Depends(get_account_manager)
):
    """
    Освободить все аккаунты, заблокированные сервисом
    """
    try:
        logger.info(f"🔓 Bulk release request for all accounts locked by {request.service_name}")
        
        # Получаем все Redis locks для данного сервиса
        lock_pattern = f"account_lock:*"
        all_locks = account_manager.redis_client.keys(lock_pattern)
        
        released_count = 0
        errors = []
        
        for lock_key in all_locks:
            lock_value = account_manager.redis_client.get(lock_key)
            
            if lock_value and lock_value.startswith(f"{request.service_name}:"):
                try:
                    # Освобождаем lock
                    account_manager.redis_client.delete(lock_key)
                    released_count += 1
                    
                    # Логируем освобождение
                    account_id = lock_key.decode('utf-8').split(':')[1] if isinstance(lock_key, bytes) else lock_key.split(':')[1]
                    logger.debug(f"🔓 Released lock for account {account_id}")
                    
                except Exception as e:
                    account_id = lock_key.decode('utf-8') if isinstance(lock_key, bytes) else str(lock_key)
                    error_msg = f"Failed to release {account_id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"❌ {error_msg}")
        
        return {
            "success": True,
            "message": f"Released {released_count} accounts locked by {request.service_name}",
            "released_count": released_count,
            "errors": errors if errors else None,
            "released_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error releasing all accounts for {request.service_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Error releasing accounts: {str(e)}")

@router.get("/debug/redis-locks")
async def debug_redis_locks(
    account_manager: AccountManagerService = Depends(get_account_manager)
):
    """
    Диагностический endpoint для проверки всех Redis locks
    """
    try:
        lock_pattern = f"account_lock:*"
        all_locks = account_manager.redis_client.keys(lock_pattern)
        
        lock_details = []
        service_breakdown = {}
        
        for lock_key in all_locks:
            lock_value = account_manager.redis_client.get(lock_key)
            ttl = account_manager.redis_client.ttl(lock_key)
            
            key_str = lock_key.decode('utf-8') if isinstance(lock_key, bytes) else lock_key
            account_id = key_str.split(':')[1] if ':' in key_str else 'unknown'
            
            if lock_value:
                service_name = lock_value.split(':')[0] if ':' in lock_value else 'unknown'
                timestamp = lock_value.split(':', 1)[1] if ':' in lock_value else 'unknown'
                
                if service_name not in service_breakdown:
                    service_breakdown[service_name] = 0
                service_breakdown[service_name] += 1
                
                lock_details.append({
                    "account_id": account_id,
                    "service_name": service_name,
                    "locked_at": timestamp,
                    "ttl_seconds": ttl,
                    "key": key_str,
                    "value": lock_value
                })
        
        return {
            "success": True,
            "total_locks": len(all_locks),
            "service_breakdown": service_breakdown,
            "lock_details": lock_details,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting Redis locks debug info: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting lock info: {str(e)}")

@router.post("/debug/clear-all-locks")
async def clear_all_redis_locks(
    account_manager: AccountManagerService = Depends(get_account_manager)
):
    """
    ЭКСТРЕННЫЙ endpoint для очистки ВСЕХ Redis locks (используйте осторожно!)
    """
    try:
        lock_pattern = f"account_lock:*"
        all_locks = account_manager.redis_client.keys(lock_pattern)
        
        cleared_count = 0
        cleared_locks = []
        
        for lock_key in all_locks:
            lock_value = account_manager.redis_client.get(lock_key)
            key_str = lock_key.decode('utf-8') if isinstance(lock_key, bytes) else lock_key
            
            cleared_locks.append({
                "key": key_str,
                "value": lock_value
            })
            
            account_manager.redis_client.delete(lock_key)
            cleared_count += 1
        
        return {
            "success": True,
            "message": f"Cleared ALL {cleared_count} Redis locks",
            "cleared_count": cleared_count,
            "cleared_locks": cleared_locks,
            "cleared_at": datetime.utcnow().isoformat(),
            "warning": "ALL account locks have been forcefully removed"
        }
        
    except Exception as e:
        logger.error(f"❌ Error clearing all Redis locks: {e}")
        raise HTTPException(status_code=500, detail=f"Error clearing locks: {str(e)}")

@router.post("/maintenance/reset-daily-limits")
async def reset_daily_limits(
    session: AsyncSession = Depends(get_async_session),
    flood_ban_manager: FloodBanManager = Depends(get_flood_ban_manager)
):
    """
    Сбросить дневные лимиты для всех аккаунтов (maintenance операция)
    """
    try:
        affected_count = await flood_ban_manager.reset_daily_limits(session)
        
        return {
            "success": True,
            "message": "Daily limits reset successfully",
            "affected_accounts": affected_count,
            "reset_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error resetting daily limits: {e}")
        raise HTTPException(status_code=500, detail=f"Error resetting daily limits: {str(e)}")

@router.post("/maintenance/process-recoveries")
async def process_pending_recoveries(
    limit: int = Query(50, description="Максимальное количество восстановлений"),
    session: AsyncSession = Depends(get_async_session),
    flood_ban_manager: FloodBanManager = Depends(get_flood_ban_manager)
):
    """
    Обработать ожидающие восстановления (maintenance операция)
    """
    try:
        processed_count = await flood_ban_manager.process_pending_recoveries(
            session=session,
            limit=limit
        )
        
        return {
            "success": True,
            "message": "Pending recoveries processed",
            "processed_count": processed_count,
            "processed_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error processing pending recoveries: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing recoveries: {str(e)}")

@router.post("/maintenance/cleanup-rate-limits")
async def cleanup_rate_limit_data(
    rate_limiting: RateLimitingService = Depends(get_rate_limiting_service)
):
    """
    Очистить устаревшие данные rate limiting (maintenance операция)
    """
    try:
        deleted_count = await rate_limiting.cleanup_expired_data()
        
        return {
            "success": True,
            "message": "Rate limiting data cleaned up",
            "deleted_keys": deleted_count,
            "cleaned_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error cleaning up rate limit data: {e}")
        raise HTTPException(status_code=500, detail=f"Error cleaning up data: {str(e)}")