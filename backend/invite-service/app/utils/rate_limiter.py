"""
Rate Limiting система для управления лимитами отправки приглашений
"""

import asyncio
import logging
import redis.asyncio as redis
from datetime import datetime, timedelta, date
from typing import Dict, Any, Optional, List
import json
import os

from app.adapters.base import PlatformAccount, AccountStatus

logger = logging.getLogger(__name__)


class RateLimiter:
    """Система rate limiting для различных платформ"""
    
    def __init__(self):
        self.redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
        self.redis_client = None
        
        # Базовые лимиты Telegram
        self.telegram_limits = {
            "daily_invites": 50,
            "daily_messages": 40,
            "hourly_invites": 5,
            "hourly_messages": 10,
            "flood_wait_buffer": 300,  # 5 минут буфер после flood wait
            "peer_flood_duration": 86400  # 24 часа для peer flood
        }
        
        logger.info("Инициализирован Rate Limiter")
    
    async def _get_redis(self) -> redis.Redis:
        """Получение Redis клиента с lazy connection"""
        if self.redis_client is None:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
        return self.redis_client
    
    async def close(self):
        """Закрытие Redis подключения"""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
    
    async def can_send_invite(self, account: PlatformAccount) -> bool:
        """Проверка возможности отправки приглашения"""
        
        if account.platform != "telegram":
            # Для других платформ пока что разрешаем
            return True
        
        try:
            redis_client = await self._get_redis()
            
            # Проверка статуса аккаунта
            if account.status != AccountStatus.ACTIVE:
                return False
            
            # Проверка flood wait
            flood_key = f"telegram:flood:{account.account_id}"
            if await redis_client.exists(flood_key):
                logger.debug(f"Аккаунт {account.account_id} находится в flood wait")
                return False
            
            # Проверка peer flood
            peer_flood_key = f"telegram:peer_flood:{account.account_id}"
            if await redis_client.exists(peer_flood_key):
                logger.debug(f"Аккаунт {account.account_id} находится в peer flood")
                return False
            
            # Проверка дневного лимита
            daily_key = f"telegram:invites:daily:{account.account_id}:{date.today()}"
            daily_count = await redis_client.get(daily_key)
            daily_used = int(daily_count) if daily_count else 0
            
            if daily_used >= account.daily_invite_limit:
                logger.debug(f"Аккаунт {account.account_id} достиг дневного лимита приглашений: {daily_used}/{account.daily_invite_limit}")
                return False
            
            # Проверка часового лимита
            current_hour = datetime.utcnow().hour
            hourly_key = f"telegram:invites:hourly:{account.account_id}:{date.today()}:{current_hour}"
            hourly_count = await redis_client.get(hourly_key)
            hourly_used = int(hourly_count) if hourly_count else 0
            
            if hourly_used >= account.hourly_invite_limit:
                logger.debug(f"Аккаунт {account.account_id} достиг часового лимита приглашений: {hourly_used}/{account.hourly_invite_limit}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка проверки возможности отправки приглашения для аккаунта {account.account_id}: {str(e)}")
            # В случае ошибки Redis возвращаем консервативное решение
            return False
    
    async def can_send_message(self, account: PlatformAccount) -> bool:
        """Проверка возможности отправки сообщения"""
        
        if account.platform != "telegram":
            return True
        
        try:
            redis_client = await self._get_redis()
            
            # Проверка статуса аккаунта
            if account.status != AccountStatus.ACTIVE:
                return False
            
            # Проверка flood wait
            flood_key = f"telegram:flood:{account.account_id}"
            if await redis_client.exists(flood_key):
                return False
            
            # Проверка дневного лимита сообщений
            daily_key = f"telegram:messages:daily:{account.account_id}:{date.today()}"
            daily_count = await redis_client.get(daily_key)
            daily_used = int(daily_count) if daily_count else 0
            
            if daily_used >= account.daily_message_limit:
                logger.debug(f"Аккаунт {account.account_id} достиг дневного лимита сообщений: {daily_used}/{account.daily_message_limit}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка проверки возможности отправки сообщения для аккаунта {account.account_id}: {str(e)}")
            return False
    
    async def record_invite(self, account: PlatformAccount) -> None:
        """Запись отправленного приглашения в статистику"""
        
        if account.platform != "telegram":
            return
        
        try:
            redis_client = await self._get_redis()
            
            # Увеличение дневного счетчика
            daily_key = f"telegram:invites:daily:{account.account_id}:{date.today()}"
            await redis_client.incr(daily_key)
            await redis_client.expire(daily_key, 86400)  # 24 часа
            
            # Увеличение часового счетчика
            current_hour = datetime.utcnow().hour
            hourly_key = f"telegram:invites:hourly:{account.account_id}:{date.today()}:{current_hour}"
            await redis_client.incr(hourly_key)
            await redis_client.expire(hourly_key, 3600)  # 1 час
            
            # Обновление времени последней активности
            activity_key = f"telegram:last_activity:{account.account_id}"
            await redis_client.set(activity_key, datetime.utcnow().isoformat(), ex=86400)
            
            logger.debug(f"Записано приглашение для аккаунта {account.account_id}")
            
        except Exception as e:
            logger.error(f"Ошибка записи приглашения для аккаунта {account.account_id}: {str(e)}")
    
    async def record_message(self, account: PlatformAccount) -> None:
        """Запись отправленного сообщения в статистику"""
        
        if account.platform != "telegram":
            return
        
        try:
            redis_client = await self._get_redis()
            
            # Увеличение дневного счетчика сообщений
            daily_key = f"telegram:messages:daily:{account.account_id}:{date.today()}"
            await redis_client.incr(daily_key)
            await redis_client.expire(daily_key, 86400)
            
            # Обновление времени последней активности
            activity_key = f"telegram:last_activity:{account.account_id}"
            await redis_client.set(activity_key, datetime.utcnow().isoformat(), ex=86400)
            
            logger.debug(f"Записано сообщение для аккаунта {account.account_id}")
            
        except Exception as e:
            logger.error(f"Ошибка записи сообщения для аккаунта {account.account_id}: {str(e)}")
    
    async def handle_flood_wait(self, account: PlatformAccount, seconds: int) -> None:
        """Обработка Telegram FloodWait ошибки"""
        
        try:
            redis_client = await self._get_redis()
            
            # Устанавливаем flood wait с буфером
            total_seconds = seconds + self.telegram_limits["flood_wait_buffer"]
            flood_key = f"telegram:flood:{account.account_id}"
            
            await redis_client.setex(flood_key, total_seconds, json.dumps({
                "original_seconds": seconds,
                "buffer_seconds": self.telegram_limits["flood_wait_buffer"],
                "started_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(seconds=total_seconds)).isoformat()
            }))
            
            # Обновляем статус аккаунта
            account.status = AccountStatus.FLOOD_WAIT
            account.flood_wait_until = datetime.utcnow() + timedelta(seconds=total_seconds)
            
            logger.warning(f"Установлен flood wait для аккаунта {account.account_id}: {seconds}s + {self.telegram_limits['flood_wait_buffer']}s буфер")
            
        except Exception as e:
            logger.error(f"Ошибка установки flood wait для аккаунта {account.account_id}: {str(e)}")
    
    async def handle_peer_flood(self, account: PlatformAccount) -> None:
        """Обработка Telegram PeerFlood ошибки"""
        
        try:
            redis_client = await self._get_redis()
            
            # Устанавливаем peer flood на 24 часа
            peer_flood_key = f"telegram:peer_flood:{account.account_id}"
            duration = self.telegram_limits["peer_flood_duration"]
            
            await redis_client.setex(peer_flood_key, duration, json.dumps({
                "started_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(seconds=duration)).isoformat(),
                "reason": "peer_flood"
            }))
            
            # Обновляем статус аккаунта
            account.status = AccountStatus.RATE_LIMITED
            
            logger.warning(f"Установлен peer flood для аккаунта {account.account_id} на {duration/3600:.1f} часов")
            
        except Exception as e:
            logger.error(f"Ошибка установки peer flood для аккаунта {account.account_id}: {str(e)}")
    
    async def get_account_usage(self, account: PlatformAccount) -> Dict[str, Any]:
        """Получение текущего использования лимитов аккаунта"""
        
        if account.platform != "telegram":
            return {}
        
        try:
            redis_client = await self._get_redis()
            
            # Дневные счетчики
            daily_invites_key = f"telegram:invites:daily:{account.account_id}:{date.today()}"
            daily_messages_key = f"telegram:messages:daily:{account.account_id}:{date.today()}"
            
            daily_invites = await redis_client.get(daily_invites_key)
            daily_messages = await redis_client.get(daily_messages_key)
            
            # Часовой счетчик
            current_hour = datetime.utcnow().hour
            hourly_invites_key = f"telegram:invites:hourly:{account.account_id}:{date.today()}:{current_hour}"
            hourly_invites = await redis_client.get(hourly_invites_key)
            
            # Ограничения
            flood_key = f"telegram:flood:{account.account_id}"
            peer_flood_key = f"telegram:peer_flood:{account.account_id}"
            
            flood_data = await redis_client.get(flood_key)
            peer_flood_data = await redis_client.get(peer_flood_key)
            
            # Последняя активность
            activity_key = f"telegram:last_activity:{account.account_id}"
            last_activity = await redis_client.get(activity_key)
            
            return {
                "daily_invites_used": int(daily_invites) if daily_invites else 0,
                "daily_messages_used": int(daily_messages) if daily_messages else 0,
                "hourly_invites_used": int(hourly_invites) if hourly_invites else 0,
                "daily_invites_remaining": max(0, account.daily_invite_limit - (int(daily_invites) if daily_invites else 0)),
                "daily_messages_remaining": max(0, account.daily_message_limit - (int(daily_messages) if daily_messages else 0)),
                "hourly_invites_remaining": max(0, account.hourly_invite_limit - (int(hourly_invites) if hourly_invites else 0)),
                "flood_wait": json.loads(flood_data) if flood_data else None,
                "peer_flood": json.loads(peer_flood_data) if peer_flood_data else None,
                "last_activity": last_activity,
                "can_send_invite": await self.can_send_invite(account),
                "can_send_message": await self.can_send_message(account)
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения использования аккаунта {account.account_id}: {str(e)}")
            return {}
    
    async def reset_hourly_limits(self) -> int:
        """Сброс часовых лимитов (вызывается по расписанию)"""
        
        try:
            redis_client = await self._get_redis()
            
            # Паттерн для часовых ключей
            pattern = f"telegram:invites:hourly:*:{date.today()}:*"
            
            # Получаем все ключи и удаляем устаревшие
            current_hour = datetime.utcnow().hour
            deleted_count = 0
            
            async for key in redis_client.scan_iter(match=pattern):
                # Проверяем час в ключе
                key_parts = key.split(":")
                if len(key_parts) >= 5:
                    key_hour = int(key_parts[4])
                    if key_hour != current_hour:
                        await redis_client.delete(key)
                        deleted_count += 1
            
            logger.info(f"Сброшено {deleted_count} устаревших часовых лимитов")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Ошибка сброса часовых лимитов: {str(e)}")
            return 0
    
    async def cleanup_expired_restrictions(self) -> int:
        """Очистка истекших ограничений"""
        
        try:
            redis_client = await self._get_redis()
            
            # Паттерны для проверки
            patterns = [
                "telegram:flood:*",
                "telegram:peer_flood:*"
            ]
            
            cleaned_count = 0
            
            for pattern in patterns:
                async for key in redis_client.scan_iter(match=pattern):
                    # Проверяем TTL ключа
                    ttl = await redis_client.ttl(key)
                    if ttl <= 0:  # Ключ истек или не имеет TTL
                        await redis_client.delete(key)
                        cleaned_count += 1
            
            if cleaned_count > 0:
                logger.info(f"Очищено {cleaned_count} истекших ограничений")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Ошибка очистки истекших ограничений: {str(e)}")
            return 0
    
    async def get_platform_stats(self, platform: str = "telegram") -> Dict[str, Any]:
        """Получение статистики по платформе"""
        
        try:
            redis_client = await self._get_redis()
            
            if platform == "telegram":
                # Паттерны для поиска
                daily_pattern = f"telegram:invites:daily:*:{date.today()}"
                flood_pattern = "telegram:flood:*"
                peer_flood_pattern = "telegram:peer_flood:*"
                
                # Подсчет активных аккаунтов
                active_accounts = 0
                total_daily_invites = 0
                
                async for key in redis_client.scan_iter(match=daily_pattern):
                    count = await redis_client.get(key)
                    if count:
                        active_accounts += 1
                        total_daily_invites += int(count)
                
                # Подсчет ограниченных аккаунтов
                flood_accounts = len([key async for key in redis_client.scan_iter(match=flood_pattern)])
                peer_flood_accounts = len([key async for key in redis_client.scan_iter(match=peer_flood_pattern)])
                
                return {
                    "platform": platform,
                    "date": date.today().isoformat(),
                    "active_accounts": active_accounts,
                    "total_daily_invites": total_daily_invites,
                    "flood_wait_accounts": flood_accounts,
                    "peer_flood_accounts": peer_flood_accounts,
                    "restricted_accounts": flood_accounts + peer_flood_accounts
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики платформы {platform}: {str(e)}")
            return {}


# Глобальный экземпляр rate limiter
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Получение глобального экземпляра rate limiter"""
    global _rate_limiter
    
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    
    return _rate_limiter


async def close_rate_limiter():
    """Закрытие глобального rate limiter"""
    global _rate_limiter
    
    if _rate_limiter:
        await _rate_limiter.close()
        _rate_limiter = None 