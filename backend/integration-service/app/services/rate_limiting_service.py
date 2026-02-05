"""
Rate Limiting System
Управление лимитами Telegram API и предотвращение нарушений.

Лимиты для приглашений (INVITE):
- daily_limit: 30 в день на аккаунт
- hourly_limit: 2 в час
- per_channel_daily: 15 в день на один канал/паблик
- cooldown_seconds: 900 (15 минут между приглашениями)
- burst_limit: 3 подряд, burst_cooldown: 900 с

Данные хранятся в Redis: db = REDIS_DB + 3 (при REDIS_DB=0 это DB 3).
Очистка только rate-limit: redis-cli -n 3 FLUSHDB (если REDIS_DB=0).
"""
import logging
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, func
import redis
import json

from ..models.telegram_sessions import TelegramSession
from ..models.account_manager_types import (
    ActionType, AccountPurpose, AccountLimits
)
from ..core.config import get_settings
from .integration_log_service import IntegrationLogService

logger = logging.getLogger(__name__)

class RateLimitingService:
    """Система управления лимитами Telegram API"""
    
    def __init__(self):
        self.settings = get_settings()
        self.log_service = IntegrationLogService()
        
        # Redis для хранения rate limiting данных
        self.redis_client = redis.Redis(
            host=self.settings.REDIS_HOST,
            port=self.settings.REDIS_PORT,
            db=self.settings.REDIS_DB + 3,  # Отдельная DB для Rate Limiting
            decode_responses=True
        )
        
        # Конфигурация лимитов Telegram API
        self.telegram_limits = {
            ActionType.INVITE: {
                'daily_limit': 30,         # 30 приглашений в день
                'hourly_limit': 2,         # 2 приглашения в час (равномерность)
                'per_channel_daily': 15,   # 15 приглашений в день на канал
                'cooldown_seconds': 900,   # 15 минут между приглашениями
                'burst_limit': 3,          # Максимум 3 приглашения подряд
                'burst_cooldown': 900      # 15 минут после burst
            },
            ActionType.MESSAGE: {
                'daily_limit': 30,         # 30 сообщений в день
                'hourly_limit': 10,        # 10 сообщений в час
                'cooldown_seconds': 60,    # 1 минута между сообщениями
                'burst_limit': 5,          # Максимум 5 сообщений подряд
                'burst_cooldown': 180      # 3 минуты после burst
            },
            ActionType.ADD_CONTACT: {
                'daily_limit': 15,         # 15 контактов в день
                'hourly_limit': 3,         # 3 контакта в час
                'cooldown_seconds': 300,   # 5 минут между добавлениями
                'burst_limit': 2,          # Максимум 2 контакта подряд
                'burst_cooldown': 600      # 10 минут после burst
            },
            ActionType.PARSE: {
                'daily_limit': 5000,       # парсинг — чтение, лимит мягкий
                'hourly_limit': 120,       # 120 операций в час
                'cooldown_seconds': 2,     # 2 сек между запросами
                'burst_limit': 20,         # до 20 подряд
                'burst_cooldown': 60       # 1 мин после burst
            }
        }
    
    def _account_available_for_action(self, account, allow_locked: bool = False) -> bool:
        """
        Доступен ли аккаунт для выполнения действия.
        
        ВАЖНО:
        - Статус 'disabled' всегда делает аккаунт недоступным.
        - Статусы 'flood_wait' / 'blocked' рассматриваются только совместно с полями
          flood_wait_until / blocked_until. Если время уже прошло — аккаунт СЧИТАЕМ
          доступным (как «вышедший из флуда/блока»), даже если статус в БД ещё не
          был обновлён обратно на 'active'.
        - DB-флаг locked больше НЕ используется как причина недоступности.
        """
        is_active = getattr(account, 'is_active', None)
        status = str(getattr(account, 'status', 'active') or 'active').lower()
        if not is_active:
            logger.info(
                f"🔍 RATE_LIMIT: Account {account.id} not available: is_active={is_active}, status={status}"
            )
            return False
        # Жёстко блокируем только явно отключённые аккаунты
        if status == 'disabled':
            logger.info(
                f"🔍 RATE_LIMIT: Account {account.id} not available: status=disabled"
            )
            return False
        now = datetime.now(timezone.utc)
        def _until_past(until_val):
            if not until_val:
                return False
            try:
                until = until_val.replace(tzinfo=timezone.utc) if getattr(until_val, 'tzinfo', None) is None else until_val
                return until > now
            except TypeError:
                return False
        try:
            if _until_past(getattr(account, 'flood_wait_until', None)):
                logger.info(f"🔍 RATE_LIMIT: Account {account.id} not available: flood_wait_until > now")
                return False
            if _until_past(getattr(account, 'blocked_until', None)):
                logger.info(f"🔍 RATE_LIMIT: Account {account.id} not available: blocked_until > now")
                return False
        except Exception as e:
            logger.warning(f"🔍 RATE_LIMIT: datetime check error for account {account.id}: {e}")
            return False

        # DB-поле locked считаем устаревшим: оно могло быть выставлено старой версией кода
        # и не отражает актуальные Redis-локи. Для диагностики просто логируем его значение,
        # но НЕ используем как причину отказа.
        locked_flag = getattr(account, 'locked', None)
        if locked_flag:
            logger.info(
                f"🔍 RATE_LIMIT: Account {account.id} has locked={locked_flag} in DB, "
                f"но DB-флаг игнорируется, используем только Redis locks в AccountManager"
            )

        return True

    async def check_rate_limit(
        self,
        session: AsyncSession,
        account_id: UUID,
        action_type: ActionType,
        target_channel_id: Optional[str] = None,
        allow_locked: bool = False
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Проверить можно ли выполнить действие с учетом лимитов
        
        Args:
            session: Database session
            account_id: ID аккаунта
            action_type: Тип действия
            target_channel_id: ID целевого канала (для приглашений)
            allow_locked: Если True, не считать аккаунт недоступным из-за lock (вызов после allocate)
        
        Returns:
            Tuple[bool, Dict]: (разрешено, детали лимитов)
        """
        try:
            logger.info(f"🔍 RATE_LIMIT check_rate_limit: account_id={account_id}, action_type={action_type}, allow_locked={allow_locked}")
            # 🔒 Защита от слишком частых вызовов check_rate_limit для одного и того же аккаунта/действия.
            # ВАЖНО: для INVITE (критические бизнес-лимиты) мы НЕ применяем синтетический cooldown,
            # чтобы не подменять реальные лимиты (daily/hourly/cooldown) и не ломать паузы между инвайтами.
            # Guard используется только для "шумных" действий (например, PARSE).
            if action_type == ActionType.PARSE:
                try:
                    now_ts = datetime.now(timezone.utc).timestamp()
                    freq_key = f"rlcheck:last_call:{account_id}:{action_type}"
                    last_ts_raw = self.redis_client.get(freq_key)
                    if last_ts_raw is not None:
                        try:
                            last_ts = float(last_ts_raw)
                            if now_ts - last_ts < 1.0:
                                cooldown_remaining = 1
                                logger.warning(
                                    "📊 RATE_LIMIT check_rate_limit THROTTLED: "
                                    f"account_id={account_id}, action_type={action_type}, "
                                    f"dt={now_ts - last_ts:.3f}s < 1.0s; returning synthetic cooldown {cooldown_remaining}s"
                                )
                                return False, {
                                    "error": "Check throttled",
                                    "cooldown_remaining": cooldown_remaining,
                                    "next_allowed_at": (
                                        datetime.fromtimestamp(now_ts, tz=timezone.utc) + timedelta(seconds=cooldown_remaining)
                                    ).isoformat()
                                }
                        except (TypeError, ValueError):
                            # Некорректное значение в Redis — просто перезапишем ниже
                            pass
                    # Обновляем отметку времени последнего вызова; TTL небольшой, чтобы ключи не копились
                    self.redis_client.set(freq_key, str(now_ts), ex=5)
                except Exception as freq_err:
                    # Никогда не ломаем основную логику rate limiting из‑за диагностики частоты
                    logger.debug(f"RATE_LIMIT check_rate_limit frequency guard error for account {account_id}: {freq_err}")

            # Получаем аккаунт
            result = await session.execute(
                select(TelegramSession).where(TelegramSession.id == account_id)
            )
            account = result.scalar_one_or_none()
            
            if not account:
                return False, {"error": "Account not found"}

            # 🔄 ЛЕНИВОЕ ВОССТАНОВЛЕНИЕ СТАТУСА:
            # Если статус flood_wait/blocked, но время уже прошло — сразу обновляем запись в БД
            # (status → active, сбрасываем соответствующее *_until), чтобы в БД всегда был
            # актуальный статус аккаунта.
            try:
                now_norm = datetime.now(timezone.utc)
                status_val = str(getattr(account, "status", "active") or "active").lower()
                flood_until = getattr(account, "flood_wait_until", None)
                blocked_until = getattr(account, "blocked_until", None)
                need_update = False
                update_values = {}

                if status_val == "flood_wait":
                    if not flood_until or (
                        isinstance(flood_until, datetime)
                        and (flood_until.tzinfo or timezone.utc) <= now_norm
                    ):
                        update_values["status"] = "active"
                        update_values["flood_wait_until"] = None
                        need_update = True

                if status_val == "blocked":
                    if blocked_until and isinstance(blocked_until, datetime):
                        blocked_norm = (
                            blocked_until.replace(tzinfo=timezone.utc)
                            if blocked_until.tzinfo is None
                            else blocked_until.astimezone(timezone.utc)
                        )
                        if blocked_norm <= now_norm:
                            update_values["status"] = "active"
                            update_values["blocked_until"] = None
                            need_update = True

                if need_update:
                    await session.execute(
                        update(TelegramSession)
                        .where(TelegramSession.id == account_id)
                        .values(**update_values)
                    )
                    await session.commit()
                    # Обновляем объект в памяти, чтобы дальнейшая логика видела новый статус
                    for k, v in update_values.items():
                        setattr(account, k, v)
                    logger.info(
                        f"🔄 RATE_LIMIT: Account {account_id} status normalized in DB: {update_values}"
                    )
            except Exception as norm_err:
                logger.warning(
                    f"⚠️ RATE_LIMIT: error normalizing account status for {account_id}: {norm_err}"
                )
            
            if not self._account_available_for_action(account, allow_locked=allow_locked):
                # Аккаунт недоступен из‑за flood_wait/blocked/неактивного статуса.
                # Возвращаем расширенные диагностические данные, чтобы клиент (Invite Service) видел реальную причину.
                details = {
                    "error": "Account not available",
                    "status": getattr(account, "status", None),
                    "is_active": getattr(account, "is_active", None),
                    "flood_wait_until": getattr(account, "flood_wait_until", None).isoformat()
                    if getattr(account, "flood_wait_until", None) else None,
                    "blocked_until": getattr(account, "blocked_until", None).isoformat()
                    if getattr(account, "blocked_until", None) else None,
                    "locked": getattr(account, "locked", None),
                }
                logger.info(
                    f"🔍 RATE_LIMIT: Account {account_id} rejected by _account_available_for_action "
                    f"(status={details['status']}, is_active={details['is_active']}, "
                    f"flood_wait_until={details['flood_wait_until']}, blocked_until={details['blocked_until']}, "
                    f"locked={details['locked']})"
                )
                return False, details
            
            limits = self.telegram_limits.get(action_type, {})
            if not limits:
                return False, {"error": f"Unknown action type: {action_type}"}
            
            # Всегда работаем с timezone-aware UTC, чтобы избежать ошибок
            # "can't compare offset-naive and offset-aware datetimes"
            now = datetime.now(timezone.utc)
            checks = {}
            
            # 0. Ленивый учёт устаревших дневных счётчиков: если reset_at в прошлом (сброс не выполнялся),
            #    считаем дневное использование нулём и сбрасываем счётчики в БД для этого аккаунта,
            #    чтобы не блокировать аккаунты навсегда (например, когда Celery Beat не запущен или аккаунт давно не использовался).
            reset_at_val = getattr(account, 'reset_at', None)
            reset_at = None
            if isinstance(reset_at_val, datetime):
                # Приводим reset_at к UTC-aware datetime
                if reset_at_val.tzinfo is None:
                    reset_at = reset_at_val.replace(tzinfo=timezone.utc)
                else:
                    reset_at = reset_at_val.astimezone(timezone.utc)

            counters_stale = reset_at is not None and now > reset_at
            if counters_stale:
                next_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                await session.execute(
                    update(TelegramSession)
                    .where(TelegramSession.id == account_id)
                    .values(
                        used_invites_today=0,
                        used_messages_today=0,
                        contacts_today=0,
                        per_channel_invites={},
                        reset_at=next_midnight
                    )
                )
                await session.flush()
                logger.info(f"🔄 Lazy reset daily limits for account {account_id} (reset_at was in the past)")
            
            # 1. Проверка дневных лимитов в базе данных
            if action_type == ActionType.INVITE:
                daily_used = 0 if counters_stale else account.used_invites_today
                daily_limit = limits['daily_limit']
                
                # Проверка лимита на канал
                if target_channel_id:
                    if counters_stale:
                        per_channel_used = 0
                    else:
                        per_channel_invites = account.per_channel_invites or {}
                        channel_data = per_channel_invites.get(target_channel_id, {'today': 0})
                        per_channel_used = channel_data.get('today', 0)
                    per_channel_limit = limits['per_channel_daily']
                    
                    if per_channel_used >= per_channel_limit:
                        return False, {
                            "error": "Per-channel daily limit exceeded",
                            "per_channel_used": per_channel_used,
                            "per_channel_limit": per_channel_limit
                        }
                    checks['per_channel'] = {
                        'used': per_channel_used,
                        'limit': per_channel_limit,
                        'remaining': per_channel_limit - per_channel_used
                    }
                
            elif action_type == ActionType.MESSAGE:
                daily_used = 0 if counters_stale else account.used_messages_today
                daily_limit = limits['daily_limit']
                
            elif action_type == ActionType.CONTACT_ADD:
                daily_used = 0 if counters_stale else account.contacts_today
                daily_limit = limits['daily_limit']
            
            elif action_type == ActionType.PARSE:
                # Для парсинга не проверяем дневные лимиты из БД, так как это чтение данных
                # Используем только часовые лимиты и cooldown для избежания конфликтов
                daily_used = 0
                daily_limit = limits['daily_limit']
            
            if action_type != ActionType.PARSE and daily_used >= daily_limit:
                logger.info(
                    f"📊 RATE_LIMIT Daily limit exceeded: account_id={account_id}, action_type={action_type}, "
                    f"daily_used={daily_used}, daily_limit={daily_limit}"
                )
                return False, {
                    "error": "Daily limit exceeded",
                    "daily_used": daily_used,
                    "daily_limit": daily_limit
                }
            
            checks['daily'] = {
                'used': daily_used,
                'limit': daily_limit,
                'remaining': daily_limit - daily_used
            }
            
            # 2. Проверка часовых лимитов в Redis
            hourly_key = f"hourly:{account_id}:{action_type}:{now.strftime('%Y-%m-%d-%H')}"
            hourly_used = int(self.redis_client.get(hourly_key) or 0)
            hourly_limit = limits['hourly_limit']
            
            if hourly_used >= hourly_limit:
                logger.info(
                    f"📊 RATE_LIMIT Hourly limit exceeded: account_id={account_id}, action_type={action_type}, "
                    f"hourly_used={hourly_used}, hourly_limit={hourly_limit}, "
                    f"key=hourly:{account_id}:{action_type}:{now.strftime('%Y-%m-%d-%H')}"
                )
                return False, {
                    "error": "Hourly limit exceeded",
                    "hourly_used": hourly_used,
                    "hourly_limit": hourly_limit
                }
            
            checks['hourly'] = {
                'used': hourly_used,
                'limit': hourly_limit,
                'remaining': hourly_limit - hourly_used
            }
            
            # 3. Проверка cooldown между действиями
            cooldown_key = f"cooldown:{account_id}:{action_type}"
            last_action_time = self.redis_client.get(cooldown_key)
            
            if last_action_time:
                try:
                    parsed = datetime.fromisoformat(last_action_time)
                    if parsed.tzinfo is None:
                        last_action = parsed.replace(tzinfo=timezone.utc)
                    else:
                        last_action = parsed.astimezone(timezone.utc)
                except Exception:
                    # Если формат некорректный или неожиданный — игнорируем cooldown
                    last_action = None

            if last_action_time and last_action is not None:
                cooldown_seconds = limits['cooldown_seconds']
                time_passed = (now - last_action).total_seconds()
                
                if time_passed < cooldown_seconds:
                    logger.info(
                        f"📊 RATE_LIMIT Cooldown active: account_id={account_id}, action_type={action_type}, "
                        f"cooldown_remaining={int(cooldown_seconds - time_passed)}s, last_action={last_action_time}"
                    )
                    return False, {
                        "error": "Cooldown period active",
                        "cooldown_remaining": int(cooldown_seconds - time_passed),
                        "next_allowed_at": (last_action + timedelta(seconds=cooldown_seconds)).isoformat()
                    }
            
            checks['cooldown'] = {
                'last_action': last_action_time,
                'cooldown_seconds': limits['cooldown_seconds'],
                'ready': True
            }
            
            # 4. Проверка burst limits
            burst_key = f"burst:{account_id}:{action_type}"
            burst_data = self.redis_client.get(burst_key)
            
            burst_info = None
            if burst_data:
                try:
                    tmp_info = json.loads(burst_data)
                    burst_start_raw = tmp_info.get('start_time')
                    if burst_start_raw:
                        parsed_start = datetime.fromisoformat(burst_start_raw)
                        if parsed_start.tzinfo is None:
                            burst_start = parsed_start.replace(tzinfo=timezone.utc)
                        else:
                            burst_start = parsed_start.astimezone(timezone.utc)
                    else:
                        burst_start = None
                    burst_info = {
                        'count': tmp_info.get('count', 0),
                        'start_time': burst_start
                    }
                except Exception:
                    burst_info = None
            
            if burst_info and burst_info['start_time'] is not None:
                burst_count = burst_info.get('count', 0)
                burst_start = burst_info['start_time']
                burst_limit = limits['burst_limit']
                burst_cooldown = limits['burst_cooldown']
                
                # Если превышен burst limit и не прошло время cooldown
                if burst_count >= burst_limit:
                    time_since_burst = (now - burst_start).total_seconds()
                    if time_since_burst < burst_cooldown:
                        return False, {
                            "error": "Burst limit exceeded",
                            "burst_count": burst_count,
                            "burst_limit": burst_limit,
                            "burst_cooldown_remaining": int(burst_cooldown - time_since_burst)
                        }
            
            checks['burst'] = {
                'count': burst_info.get('count', 0) if burst_info else 0,
                'limit': limits['burst_limit'],
                'within_limit': True
            }
            
            return True, {
                "allowed": True,
                "checks": checks,
                "limits": limits
            }
            
        except Exception as e:
            logger.error(f"❌ Error checking rate limit for account {account_id}: {e}")
            return False, {"error": f"Rate limit check error: {str(e)}"}
    
    async def record_action(
        self,
        session: AsyncSession,
        account_id: UUID,
        action_type: ActionType,
        target_channel_id: Optional[str] = None,
        success: bool = True
    ) -> bool:
        """
        Записать выполненное действие и обновить лимиты.
        
        ВАЖНО: Telegram учитывает ЛЮБУЮ попытку (успешную или с бизнес‑ошибкой)
        в своих антиспам‑лимитах. Поэтому мы считаем любую попытку INVITE/MESSAGE/ADD_CONTACT
        потреблением лимита и выставляем cooldown, чтобы не было серий 4xx/5xx без пауз.
        """
        try:
            now = datetime.utcnow()
            
            # 1. Обновляем дневные лимиты в базе данных (для любой попытки, не только success=True)
            update_values = {}
            
            if action_type == ActionType.INVITE:
                update_values['used_invites_today'] = TelegramSession.used_invites_today + 1
                
                # Обновляем per-channel статистику
                if target_channel_id:
                    result = await session.execute(
                        select(TelegramSession.per_channel_invites)
                        .where(TelegramSession.id == account_id)
                    )
                    current_per_channel = result.scalar() or {}
                    
                    if target_channel_id not in current_per_channel:
                        current_per_channel[target_channel_id] = {'today': 0, 'total': 0}
                    
                    current_per_channel[target_channel_id]['today'] += 1
                    current_per_channel[target_channel_id]['total'] += 1
                    
                    update_values['per_channel_invites'] = current_per_channel
                
            elif action_type == ActionType.MESSAGE:
                update_values['used_messages_today'] = TelegramSession.used_messages_today + 1
                
            elif action_type == ActionType.ADD_CONTACT:
                update_values['contacts_today'] = TelegramSession.contacts_today + 1
            
            if action_type != ActionType.PARSE:
                update_values['last_used_at'] = now
            else:
                update_values['last_used_at'] = now
            
            # Сбрасываем счетчик ошибок при успешном действии
            update_values['error_count'] = 0
            
            # Применяем обновления в базе данных
            if update_values:
                await session.execute(
                    update(TelegramSession)
                    .where(TelegramSession.id == account_id)
                    .values(**update_values)
                )
                await session.commit()
            
            # 2. Обновляем часовые лимиты в Redis (только при успехе)
            hourly_key = f"hourly:{account_id}:{action_type}:{now.strftime('%Y-%m-%d-%H')}"
            self.redis_client.incr(hourly_key)
            self.redis_client.expire(hourly_key, 3600)
            
            # 3. Обновляем cooldown (только при успехе)
            cooldown_key = f"cooldown:{account_id}:{action_type}"
            limits = self.telegram_limits[action_type]
            self.redis_client.setex(
                cooldown_key,
                limits['cooldown_seconds'],
                now.isoformat()
            )
            
            # 4. Обновляем burst tracking (только при успехе)
            burst_key = f"burst:{account_id}:{action_type}"
            burst_data = self.redis_client.get(burst_key)
            
            if burst_data:
                burst_info = json.loads(burst_data)
                burst_start = datetime.fromisoformat(burst_info['start_time'])
                
                if (now - burst_start).total_seconds() > limits['burst_cooldown']:
                    burst_info = {'count': 1, 'start_time': now.isoformat()}
                else:
                    burst_info['count'] += 1
            else:
                burst_info = {'count': 1, 'start_time': now.isoformat()}
            
            self.redis_client.setex(
                burst_key,
                limits['burst_cooldown'],
                json.dumps(burst_info)
            )
            
            # 5. Логируем действие
            await self.log_service.log_integration_action(
                session=session,
                user_id=0,  # Получим из аккаунта если нужно
                integration_type="telegram",
                action=f"rate_limit_{action_type}_recorded",
                status="success" if success else "error",
                details={
                    "account_id": str(account_id),
                    "action_type": action_type,
                    "target_channel_id": target_channel_id,
                    "success": success,
                    "updates": list(update_values.keys())
                }
            )
            
            logger.debug(f"📊 Recorded {action_type} for account {account_id}, success: {success}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error recording action for account {account_id}: {e}")
            return False
    
    async def get_account_limits_status(
        self,
        session: AsyncSession,
        account_id: UUID
    ) -> Dict[str, Any]:
        """
        Получить текущий статус лимитов аккаунта
        
        Args:
            session: Database session
            account_id: ID аккаунта
        
        Returns:
            Dict: Подробная информация о лимитах
        """
        try:
            # Получаем аккаунт
            result = await session.execute(
                select(TelegramSession).where(TelegramSession.id == account_id)
            )
            account = result.scalar_one_or_none()
            
            if not account:
                return {"error": "Account not found"}
            
            now = datetime.utcnow()
            status = {
                "account_id": str(account_id),
                "is_available": account.is_available,
                "daily_limits": {},
                "hourly_limits": {},
                "cooldowns": {},
                "burst_status": {}
            }
            
            # Проверяем каждый тип действия
            for action_type in [ActionType.INVITE, ActionType.MESSAGE, ActionType.ADD_CONTACT, ActionType.PARSE]:
                limits = self.telegram_limits.get(action_type)
                if not limits:
                    continue
                
                # Дневные лимиты
                if action_type == ActionType.INVITE:
                    daily_used = account.used_invites_today
                elif action_type == ActionType.MESSAGE:
                    daily_used = account.used_messages_today
                elif action_type == ActionType.ADD_CONTACT:
                    daily_used = account.contacts_today
                elif action_type == ActionType.PARSE:
                    # Для парсинга не отслеживаем дневные лимиты в БД (чтение данных)
                    daily_used = 0
                
                daily_limit = limits['daily_limit']
                status["daily_limits"][action_type] = {
                    'used': daily_used,
                    'limit': daily_limit,
                    'remaining': daily_limit - daily_used,
                    'percentage': (daily_used / daily_limit) * 100 if daily_limit > 0 else 0
                }
                
                # Часовые лимиты
                hourly_key = f"hourly:{account_id}:{action_type}:{now.strftime('%Y-%m-%d-%H')}"
                hourly_used = int(self.redis_client.get(hourly_key) or 0)
                hourly_limit = limits['hourly_limit']
                status["hourly_limits"][action_type] = {
                    'used': hourly_used,
                    'limit': hourly_limit,
                    'remaining': hourly_limit - hourly_used,
                    'percentage': (hourly_used / hourly_limit) * 100 if hourly_limit > 0 else 0
                }
                
                # Cooldowns
                cooldown_key = f"cooldown:{account_id}:{action_type}"
                last_action_time = self.redis_client.get(cooldown_key)
                cooldown_seconds = limits['cooldown_seconds']
                
                if last_action_time:
                    last_action = datetime.fromisoformat(last_action_time)
                    time_passed = (now - last_action).total_seconds()
                    remaining_cooldown = max(0, cooldown_seconds - time_passed)
                    
                    status["cooldowns"][action_type] = {
                        'last_action': last_action_time,
                        'cooldown_seconds': cooldown_seconds,
                        'remaining_seconds': int(remaining_cooldown),
                        'ready': remaining_cooldown == 0,
                        'next_allowed_at': (last_action + timedelta(seconds=cooldown_seconds)).isoformat() if remaining_cooldown > 0 else None
                    }
                else:
                    status["cooldowns"][action_type] = {
                        'ready': True,
                        'remaining_seconds': 0
                    }
                
                # Burst status
                burst_key = f"burst:{account_id}:{action_type}"
                burst_data = self.redis_client.get(burst_key)
                
                if burst_data:
                    burst_info = json.loads(burst_data)
                    burst_start = datetime.fromisoformat(burst_info['start_time'])
                    burst_count = burst_info['count']
                    burst_limit = limits['burst_limit']
                    burst_cooldown = limits['burst_cooldown']
                    
                    time_since_burst = (now - burst_start).total_seconds()
                    remaining_burst_cooldown = max(0, burst_cooldown - time_since_burst)
                    
                    status["burst_status"][action_type] = {
                        'count': burst_count,
                        'limit': burst_limit,
                        'remaining_in_burst': max(0, burst_limit - burst_count),
                        'burst_start': burst_info['start_time'],
                        'cooldown_remaining': int(remaining_burst_cooldown),
                        'burst_available': burst_count < burst_limit and remaining_burst_cooldown == 0
                    }
                else:
                    status["burst_status"][action_type] = {
                        'count': 0,
                        'limit': limits['burst_limit'],
                        'remaining_in_burst': limits['burst_limit'],
                        'burst_available': True
                    }
            
            # Per-channel limits для приглашений
            if account.per_channel_invites:
                status["per_channel_limits"] = {}
                for channel_id, channel_data in account.per_channel_invites.items():
                    per_channel_limit = self.telegram_limits[ActionType.INVITE]['per_channel_daily']
                    today_used = channel_data.get('today', 0)
                    
                    status["per_channel_limits"][channel_id] = {
                        'used_today': today_used,
                        'limit': per_channel_limit,
                        'remaining': per_channel_limit - today_used,
                        'total_sent': channel_data.get('total', 0)
                    }
            
            return status
            
        except Exception as e:
            logger.error(f"❌ Error getting limits status for account {account_id}: {e}")
            return {"error": f"Error getting limits status: {str(e)}"}
    
    async def wait_for_rate_limit(
        self,
        session: AsyncSession,
        account_id: UUID,
        action_type: ActionType,
        max_wait_seconds: int = 300
    ) -> bool:
        """
        Ожидать пока не станет доступно выполнение действия
        
        Args:
            session: Database session
            account_id: ID аккаунта
            action_type: Тип действия
            max_wait_seconds: Максимальное время ожидания
        
        Returns:
            bool: True если стало доступно, False если превышено время ожидания
        """
        try:
            start_time = datetime.utcnow()
            
            while True:
                allowed, details = await self.check_rate_limit(session, account_id, action_type)
                
                if allowed:
                    return True
                
                # Проверяем время ожидания
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                if elapsed >= max_wait_seconds:
                    logger.warning(f"⏰ Rate limit wait timeout for account {account_id}, action: {action_type}")
                    return False
                
                # Определяем время следующей проверки
                wait_time = 10  # По умолчанию 10 секунд
                
                if "cooldown_remaining" in details:
                    wait_time = min(details["cooldown_remaining"] + 1, 60)
                elif "burst_cooldown_remaining" in details:
                    wait_time = min(details["burst_cooldown_remaining"] + 1, 60)
                
                logger.info(f"⏳ Waiting {wait_time}s for rate limit, account: {account_id}, action: {action_type}")
                await asyncio.sleep(wait_time)
                
        except Exception as e:
            logger.error(f"❌ Error waiting for rate limit: {e}")
            return False
    
    async def cleanup_expired_data(self) -> int:
        """
        Очистить устаревшие данные rate limiting в Redis
        
        Returns:
            int: Количество удаленных ключей
        """
        try:
            logger.info("🧹 Cleaning up expired rate limiting data")
            
            # Получаем все ключи rate limiting
            patterns = [
                "hourly:*",
                "cooldown:*",
                "burst:*"
            ]
            
            deleted_count = 0
            for pattern in patterns:
                keys = self.redis_client.keys(pattern)
                if keys:
                    # Redis автоматически удаляет ключи с истекшим TTL,
                    # но мы можем принудительно очистить старые данные
                    for key in keys:
                        ttl = self.redis_client.ttl(key)
                        if ttl == -1:  # Ключ без TTL (не должно быть)
                            self.redis_client.delete(key)
                            deleted_count += 1
            
            if deleted_count > 0:
                logger.info(f"✅ Cleaned up {deleted_count} expired rate limiting keys")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up rate limiting data: {e}")
            return 0