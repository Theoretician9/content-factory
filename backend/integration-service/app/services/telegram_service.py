from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PasswordHashInvalidError
from telethon.sessions import StringSession
import asyncio
import logging
import base64
import qrcode
import io
from uuid import UUID
import json
import redis
import os

from .base import BaseCRUDService
from .integration_log_service import IntegrationLogService
from ..models.telegram_sessions import TelegramSession
from ..models.telegram_bots import TelegramBot
from ..models.telegram_channels import TelegramChannel
from ..schemas.telegram import (
    TelegramAuthRequest, 
    TelegramConnectResponse,
    TelegramBotCreate,
    TelegramChannelCreate,
    SendMessageRequest,
    SendMessageResponse
)
from ..core.config import get_settings
from ..core.vault import IntegrationVaultClient

logger = logging.getLogger(__name__)

class TelegramService:
    """Сервис для работы с Telegram интеграцией"""
    
    def __init__(self):
        self.settings = get_settings()
        self.vault_client = IntegrationVaultClient()
        self.session_service = BaseCRUDService(TelegramSession)
        self.bot_service = BaseCRUDService(TelegramBot)
        self.channel_service = BaseCRUDService(TelegramChannel)
        self.log_service = IntegrationLogService()
        
        # Redis для временного хранения phone_code_hash
        self.redis_client = redis.Redis(
            host=self.settings.REDIS_HOST,
            port=self.settings.REDIS_PORT,
            db=self.settings.REDIS_DB,
            decode_responses=True
        )
        
        # Активные клиенты для переиспользования
        self._active_clients: Dict[str, TelegramClient] = {}
        
    async def _get_api_credentials(self) -> Tuple[str, str]:
        """Получение API ID и Hash из Vault"""
        try:
            credentials = self.vault_client.get_integration_credentials('telegram')
            api_id = credentials.get('api_id')
            api_hash = credentials.get('api_hash')
            
            if not api_id or not api_hash:
                raise ValueError("Telegram API credentials not found in Vault")
                
            return api_id, api_hash
        except Exception as e:
            logger.error(f"Error getting Telegram credentials from Vault: {e}")
            
            # Fallback к настройкам
            if self.settings.TELEGRAM_API_ID and self.settings.TELEGRAM_API_HASH:
                logger.info("Using Telegram credentials from settings")
                return self.settings.TELEGRAM_API_ID, self.settings.TELEGRAM_API_HASH
            
            # Прямой fallback к переменным окружения (hotfix)
            env_api_id = os.getenv('TELEGRAM_API_ID')
            env_api_hash = os.getenv('TELEGRAM_API_HASH')
            
            if env_api_id and env_api_hash:
                logger.info("Using Telegram credentials from environment variables")
                return env_api_id, env_api_hash
            
            raise ValueError("No Telegram API credentials found anywhere!")
    
    async def _create_client(self, session_string: Optional[str] = None) -> TelegramClient:
        """Создание Telegram клиента"""
        api_id, api_hash = await self._get_api_credentials()
        
        session = StringSession(session_string) if session_string else StringSession()
        client = TelegramClient(session, api_id, api_hash)
        
        return client
    
    async def _encrypt_session_data(self, session_data: str) -> str:
        """Шифрование данных сессии через Vault Transit"""
        try:
            # В реальной реализации используем Vault Transit для шифрования
            # Пока что возвращаем base64 encoded
            return base64.b64encode(session_data.encode()).decode()
        except Exception as e:
            logger.error(f"Error encrypting session data: {e}")
            raise
    
    async def _decrypt_session_data(self, encrypted_data: str) -> str:
        """Расшифровка данных сессии"""
        try:
            # В реальной реализации используем Vault Transit для расшифровки
            return base64.b64decode(encrypted_data.encode()).decode()
        except Exception as e:
            logger.error(f"Error decrypting session data: {e}")
            raise
    
    async def connect_account(
        self,
        session: AsyncSession,
        user_id: int,
        auth_request: TelegramAuthRequest
    ) -> TelegramConnectResponse:
        """Подключение Telegram аккаунта"""
        
        try:
            # Логируем попытку подключения
            await self.log_service.log_action(
                session, user_id, "telegram", "connect_start", "pending",
                details={"phone": auth_request.phone}
            )
            
            client = await self._create_client()
            await client.connect()
            
            # Проверяем, авторизован ли уже
            if await client.is_user_authorized():
                # Пользователь уже авторизован
                session_string = client.session.save()
                encrypted_session = await self._encrypt_session_data(session_string)
                
                # Сохраняем сессию
                session_data = {
                    "user_id": user_id,
                    "phone": auth_request.phone,
                    "session_data": {"encrypted_session": encrypted_session},
                    "session_metadata": {"method": "existing_session"}
                }
                
                telegram_session = await self.session_service.create(session, session_data)
                
                await self.log_service.log_action(
                    session, user_id, "telegram", "connect_success", "success",
                    details={"session_id": str(telegram_session.id)}
                )
                
                await client.disconnect()
                
                return TelegramConnectResponse(
                    status="success",
                    session_id=telegram_session.id,
                    message="Аккаунт успешно подключен"
                )
            
            # Ключ для хранения phone_code_hash в Redis
            redis_key = f"telegram_code_hash:{user_id}:{auth_request.phone}"
            
            # Если есть код, пытаемся войти
            if auth_request.code:
                try:
                    # Получаем phone_code_hash из Redis
                    phone_code_hash = self.redis_client.get(redis_key)
                    
                    logger.info(f"Looking for Redis key: {redis_key}")
                    logger.info(f"Found phone_code_hash: {phone_code_hash[:10] if phone_code_hash else 'None'}...")
                    
                    if not phone_code_hash:
                        logger.warning(f"No phone_code_hash found in Redis for key: {redis_key}")
                        return TelegramConnectResponse(
                            status="code_required",
                            message="Код истек. Запросите новый код"
                        )
                    
                    logger.info(f"Attempting sign_in with phone: {auth_request.phone}, code: {auth_request.code}, hash: {phone_code_hash[:10]}...")
                    
                    # Входим с кодом и phone_code_hash
                    await client.sign_in(
                        phone=auth_request.phone,
                        code=auth_request.code,
                        phone_code_hash=phone_code_hash
                    )
                    
                    session_string = client.session.save()
                    encrypted_session = await self._encrypt_session_data(session_string)
                    
                    session_data = {
                        "user_id": user_id,
                        "phone": auth_request.phone,
                        "session_data": {"encrypted_session": encrypted_session},
                        "session_metadata": {"method": "sms_code"}
                    }
                    
                    telegram_session = await self.session_service.create(session, session_data)
                    
                    await self.log_service.log_action(
                        session, user_id, "telegram", "connect_success", "success",
                        details={"session_id": str(telegram_session.id)}
                    )
                    
                    # Удаляем phone_code_hash из Redis после успешного входа
                    self.redis_client.delete(redis_key)
                    
                    await client.disconnect()
                    
                    return TelegramConnectResponse(
                        status="success",
                        session_id=telegram_session.id,
                        message="Аккаунт успешно подключен"
                    )
                    
                except SessionPasswordNeededError:
                    await client.disconnect()
                    return TelegramConnectResponse(
                        status="2fa_required",
                        message="Требуется двухфакторная аутентификация"
                    )
                except PhoneCodeInvalidError:
                    await client.disconnect()
                    return TelegramConnectResponse(
                        status="code_required",
                        message="Неверный код. Попробуйте еще раз"
                    )
            
            # Если есть пароль для 2FA
            if auth_request.password:
                try:
                    await client.sign_in(password=auth_request.password)
                    
                    session_string = client.session.save()
                    encrypted_session = await self._encrypt_session_data(session_string)
                    
                    session_data = {
                        "user_id": user_id,
                        "phone": auth_request.phone,
                        "session_data": {"encrypted_session": encrypted_session},
                        "session_metadata": {"method": "2fa_password"}
                    }
                    
                    telegram_session = await self.session_service.create(session, session_data)
                    
                    await self.log_service.log_action(
                        session, user_id, "telegram", "connect_success", "success",
                        details={"session_id": str(telegram_session.id)}
                    )
                    
                    # Удаляем phone_code_hash из Redis после успешного входа
                    self.redis_client.delete(redis_key)
                    
                    await client.disconnect()
                    
                    return TelegramConnectResponse(
                        status="success",
                        session_id=telegram_session.id,
                        message="Аккаунт успешно подключен"
                    )
                    
                except PasswordHashInvalidError:
                    await client.disconnect()
                    return TelegramConnectResponse(
                        status="2fa_required",
                        message="Неверный пароль двухфакторной аутентификации"
                    )
            
            # Отправляем SMS код
            sent_code = await client.send_code_request(auth_request.phone)
            
            # Сохраняем phone_code_hash в Redis с TTL 15 минут
            self.redis_client.setex(
                redis_key,
                900,  # 15 минут
                sent_code.phone_code_hash
            )
            
            logger.info(f"Saved phone_code_hash to Redis: {redis_key}, hash: {sent_code.phone_code_hash[:10]}...")
            
            await client.disconnect()
            
            return TelegramConnectResponse(
                status="code_required",
                message=f"Код отправлен на номер {auth_request.phone}"
            )
            
        except Exception as e:
            logger.error(f"Error connecting Telegram account: {e}")
            
            await self.log_service.log_action(
                session, user_id, "telegram", "connect_error", "error",
                details={"phone": auth_request.phone},
                error_message=str(e)
            )
            
            return TelegramConnectResponse(
                status="error",
                message=f"Ошибка подключения: {str(e)}"
            )
    
    async def get_user_sessions(
        self,
        session: AsyncSession,
        user_id: int,
        active_only: bool = True
    ) -> List[TelegramSession]:
        """Получение сессий пользователя"""
        filters = {"user_id": user_id}
        if active_only:
            filters["is_active"] = True
            
        return await self.session_service.get_multi(session, filters=filters)
    
    async def disconnect_session(
        self,
        session: AsyncSession,
        user_id: int,
        session_id: UUID
    ) -> bool:
        """Отключение Telegram сессии"""
        try:
            # Получаем сессию
            telegram_session = await self.session_service.get_by_id(session, session_id)
            
            if not telegram_session or telegram_session.user_id != user_id:
                return False
            
            # Деактивируем сессию
            await self.session_service.update(
                session, session_id, {"is_active": False}
            )
            
            # Удаляем из активных клиентов
            client_key = f"{user_id}_{session_id}"
            if client_key in self._active_clients:
                await self._active_clients[client_key].disconnect()
                del self._active_clients[client_key]
            
            await self.log_service.log_action(
                session, user_id, "telegram", "disconnect", "success",
                details={"session_id": str(session_id)}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error disconnecting session: {e}")
            
            await self.log_service.log_action(
                session, user_id, "telegram", "disconnect_error", "error",
                details={"session_id": str(session_id)},
                error_message=str(e)
            )
            
            return False
    
    async def generate_qr_code(self, user_id: int) -> str:
        """Генерация QR кода для входа"""
        try:
            client = await self._create_client()
            await client.connect()
            
            # Получаем QR код для входа
            qr_login = await client.qr_login()
            
            # Создаем QR код
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(qr_login.url)
            qr.make(fit=True)
            
            # Конвертируем в base64
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            await client.disconnect()
            
            return qr_code_base64
            
        except Exception as e:
            logger.error(f"Error generating QR code: {e}")
            raise 