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
import time

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

# Глобальное хранилище активных клиентов авторизации (не теряется между HTTP запросами)
_GLOBAL_AUTH_SESSIONS: Dict[str, Dict] = {}

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
        # Активные auth sessions хранятся в глобальной переменной _GLOBAL_AUTH_SESSIONS
        # чтобы не теряться между HTTP запросами (FastAPI создает новый сервис для каждого запроса)
        
    async def _get_api_credentials(self) -> Tuple[str, str]:
        """Получение API ID и Hash из Vault"""
        try:
            credentials = self.vault_client.get_integration_credentials('telegram')
            api_id = credentials.get('api_id')
            api_hash = credentials.get('api_hash')
            
            logger.info(f"Retrieved credentials from Vault - API ID: {api_id}, Hash: {api_hash[:10]}...")
            
            if not api_id or not api_hash:
                logger.error("Telegram API credentials not found in Vault")
                raise ValueError("Telegram API credentials not found in Vault")
                
            return api_id, api_hash
        except Exception as e:
            logger.error(f"Error getting Telegram credentials from Vault: {e}")
            
            # Fallback к настройкам
            if self.settings.TELEGRAM_API_ID and self.settings.TELEGRAM_API_HASH:
                logger.info(f"Using Telegram credentials from settings - API ID: {self.settings.TELEGRAM_API_ID}")
                return self.settings.TELEGRAM_API_ID, self.settings.TELEGRAM_API_HASH
            
            # Прямой fallback к переменным окружения (hotfix)
            env_api_id = os.getenv('TELEGRAM_API_ID')
            env_api_hash = os.getenv('TELEGRAM_API_HASH')
            
            if env_api_id and env_api_hash:
                logger.info(f"Using Telegram credentials from environment variables - API ID: {env_api_id}")
                return env_api_id, env_api_hash
            
            raise ValueError("No Telegram API credentials found anywhere!")
    
    async def _create_client(self, session_string: Optional[str] = None) -> TelegramClient:
        """Создание Telegram клиента"""
        api_id, api_hash = await self._get_api_credentials()
        
        # Проверяем формат api_id
        try:
            api_id = int(api_id)
        except ValueError:
            logger.error(f"Invalid API ID format: {api_id}")
            raise ValueError("Invalid API ID format")
        
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
        """Подключение Telegram аккаунта с единой сессией"""
        
        # Очищаем старые auth sessions
        self._cleanup_old_auth_sessions()
        
        auth_key = f"auth_{user_id}_{auth_request.phone}"
        
        try:
            # Логируем попытку подключения
            await self.log_service.log_action(
                session, user_id, "telegram", "connect_start", "pending",
                details={"phone": auth_request.phone}
            )
            
            # Если есть код, пытаемся войти с существующим клиентом
            if auth_request.code:
                auth_data = await self._get_auth_session(auth_key)
                
                if not auth_data:
                    return TelegramConnectResponse(
                        status="code_required",
                        message="Сессия авторизации истекла. Запросите новый код"
                    )
                
                current_timestamp = int(time.time())
                request_timestamp = auth_data.get('timestamp', 0)
                elapsed_seconds = current_timestamp - request_timestamp
                
                logger.info(f"Attempting sign_in with restored session. Phone: {auth_request.phone}, code: {auth_request.code}, elapsed: {elapsed_seconds}s")
                
                try:
                    # Если в auth_data есть активный клиент - используем его
                    if 'client' in auth_data:
                        client = auth_data['client']
                        phone_code_hash = auth_data['phone_code_hash']
                        logger.info(f"Using active client from memory for sign_in")
                    else:
                        # Восстанавливаем клиент из сохраненной сессии (из Redis)
                        client = await self._create_client_from_session(auth_data['session_string'])
                        phone_code_hash = auth_data['phone_code_hash']
                        logger.info(f"Restored client from Redis session for sign_in")
                    
                    # Входим с кодом
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
                        "session_metadata": {"method": "sms_code_redis", "elapsed_seconds": elapsed_seconds}
                    }
                    
                    telegram_session = await self.session_service.create(session, session_data)
                    
                    await self.log_service.log_action(
                        session, user_id, "telegram", "connect_success", "success",
                        details={"session_id": str(telegram_session.id), "elapsed_seconds": elapsed_seconds}
                    )
                    
                    # Очищаем auth session
                    await client.disconnect()
                    await self._delete_auth_session(auth_key)
                    
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
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Error during sign_in: {e}")
                    
                    # Очищаем сессию при ошибке
                    await client.disconnect()
                    await self._delete_auth_session(auth_key)
                    
                    if "confirmation code has expired" in error_msg.lower():
                        return TelegramConnectResponse(
                            status="code_expired",
                            message="Код подтверждения истек. Запросите новый код"
                        )
                    elif "phone code invalid" in error_msg.lower():
                        return TelegramConnectResponse(
                            status="code_invalid",
                            message="Неверный код. Проверьте и попробуйте еще раз"
                        )
                    else:
                        return TelegramConnectResponse(
                            status="error",
                            message=f"Ошибка входа: {error_msg}"
                        )
            
            # Если есть пароль для 2FA
            if auth_request.password:
                auth_data = await self._get_auth_session(auth_key)
                
                if not auth_data:
                    return TelegramConnectResponse(
                        status="code_required", 
                        message="Сначала запросите SMS код"
                    )
                
                try:
                    client = await self._create_client_from_session(auth_data['session_string'])
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
                    
                    # Очищаем auth session
                    await client.disconnect()
                    await self._delete_auth_session(auth_key)
                    
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
            
            # Проверяем есть ли уже активная auth session (защита от спама)
            existing_auth = await self._get_auth_session(auth_key)
            if existing_auth:
                request_timestamp = existing_auth.get('timestamp', 0)
                elapsed = int(time.time()) - request_timestamp
                if elapsed < 60:  # Если запрос был меньше минуты назад
                    return TelegramConnectResponse(
                        status="code_required",
                        message=f"Код уже отправлен. Повторный запрос возможен через {60 - elapsed} секунд"
                    )
            
            # Первичный запрос: создаем клиент и запрашиваем код
            client = await self._create_client()
            await client.connect()
            
            # Проверяем, авторизован ли уже
            if await client.is_user_authorized():
                session_string = client.session.save()
                encrypted_session = await self._encrypt_session_data(session_string)
                
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
            
            # Отправляем код
            logger.info(f"Sending code to {auth_request.phone}...")
            
            try:
                # Отправляем код через приложение Telegram
                sent_code = await client.send_code_request(
                    phone=auth_request.phone,
                    force_sms=False  # Явно указываем, что не хотим принудительно SMS
                )
                
                # Детальное логирование ответа от Telegram
                logger.info(f"Code sent successfully!")
                logger.info(f"Code type: {getattr(sent_code, 'type', 'unknown')}")
                logger.info(f"Next type: {getattr(sent_code, 'next_type', 'unknown')}")
                logger.info(f"Timeout: {getattr(sent_code, 'timeout', 'unknown')} seconds")
                logger.info(f"Phone code hash: {sent_code.phone_code_hash[:15]}...")
                
                # Определяем тип кода для пользователя
                code_type = getattr(sent_code, 'type', None)
                if hasattr(code_type, '__class__'):
                    type_name = code_type.__class__.__name__
                    if type_name == 'SentCodeTypeApp':
                        message = f"Код отправлен в приложение Telegram на номере {auth_request.phone}. Проверьте уведомления в приложении Telegram."
                    elif type_name == 'SentCodeTypeSms':
                        message = f"SMS код отправлен на номер {auth_request.phone}. Введите код в течение 5 минут."
                    elif type_name == 'SentCodeTypeCall':
                        message = f"Код будет передан голосовым звонком на номер {auth_request.phone}."
                    else:
                        message = f"Код отправлен на номер {auth_request.phone}. Проверьте SMS или приложение Telegram."
                else:
                    message = f"Код отправлен на номер {auth_request.phone}. Проверьте SMS или приложение Telegram."
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error sending code: {error_msg}")
                
                if "phone number invalid" in error_msg.lower():
                    return TelegramConnectResponse(
                        status="error",
                        message="Неверный формат номера телефона"
                    )
                elif "wait of" in error_msg.lower():
                    wait_time = int(error_msg.split("wait of ")[1].split(" seconds")[0])
                    minutes = wait_time // 60
                    return TelegramConnectResponse(
                        status="error",
                        message=f"Слишком много попыток. Подождите {minutes} минут"
                    )
                else:
                    return TelegramConnectResponse(
                        status="error",
                        message=f"Ошибка отправки кода: {error_msg}"
                    )
            
            # Сохраняем активную сессию авторизации в Redis
            await self._save_auth_session(auth_key, client, sent_code.phone_code_hash)
            
            # ВАЖНО: Отключаем клиент после отправки кода - это НУЖНО для доставки SentCodeTypeApp!
            await client.disconnect()
            
            current_timestamp = int(time.time())
            logger.info(f"Started auth session for {auth_request.phone}, hash: {sent_code.phone_code_hash[:10]}..., timestamp: {current_timestamp}")
            
            return TelegramConnectResponse(
                status="code_required",
                message=message
            )
            
        except Exception as e:
            logger.error(f"Error connecting Telegram account: {e}")
            
            # Очищаем сессию при ошибке
            await self._delete_auth_session(auth_key)
            
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
            
            # Получаем QR код для входа (добавляем await)
            qr_login = await client.qr_login()
            
            # Сохраняем qr_login в Redis для последующей проверки авторизации
            redis_key = f"telegram_qr_login:{user_id}"
            self.redis_client.setex(redis_key, 300, str(qr_login.token.hex()))  # 5 минут
            
            logger.info(f"Generated QR code for user {user_id}, token saved to Redis")
            
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
    
    async def check_qr_authorization(
        self,
        session: AsyncSession,
        user_id: int
    ) -> TelegramConnectResponse:
        """Проверка авторизации по QR коду"""
        try:
            redis_key = f"telegram_qr_login:{user_id}"
            token_hex = self.redis_client.get(redis_key)
            
            if not token_hex:
                return TelegramConnectResponse(
                    status="qr_expired",
                    message="QR код истек. Сгенерируйте новый"
                )
            
            client = await self._create_client()
            await client.connect()
            
            # Проверяем авторизацию
            if await client.is_user_authorized():
                # Пользователь авторизован
                session_string = client.session.save()
                encrypted_session = await self._encrypt_session_data(session_string)
                
                # Получаем информацию о пользователе
                me = await client.get_me()
                phone = getattr(me, 'phone', 'unknown')
                
                session_data = {
                    "user_id": user_id,
                    "phone": phone,
                    "session_data": {"encrypted_session": encrypted_session},
                    "session_metadata": {"method": "qr_code", "telegram_id": me.id}
                }
                
                telegram_session = await self.session_service.create(session, session_data)
                
                await self.log_service.log_action(
                    session, user_id, "telegram", "qr_connect_success", "success",
                    details={"session_id": str(telegram_session.id), "telegram_id": me.id}
                )
                
                # Удаляем токен из Redis
                self.redis_client.delete(redis_key)
                
                await client.disconnect()
                
                return TelegramConnectResponse(
                    status="success",
                    session_id=telegram_session.id,
                    message="Аккаунт успешно подключен через QR код"
                )
            else:
                await client.disconnect()
                return TelegramConnectResponse(
                    status="qr_waiting",
                    message="Ожидание авторизации по QR коду"
                )
                
        except Exception as e:
            logger.error(f"Error checking QR authorization: {e}")
            return TelegramConnectResponse(
                status="error",
                message=f"Ошибка проверки QR авторизации: {str(e)}"
            ) 

    async def _save_auth_session(self, auth_key: str, client: TelegramClient, phone_code_hash: str) -> None:
        """Сохранение состояния авторизации в Redis И в глобальной памяти"""
        try:
            session_string = client.session.save()
            auth_data = {
                'session_string': session_string,
                'phone_code_hash': phone_code_hash,
                'timestamp': int(time.time())
            }
            
            # Сохраняем в Redis на 5 минут
            redis_key = f"auth_session:{auth_key}"
            self.redis_client.setex(redis_key, 300, json.dumps(auth_data))
            
            # ТАКЖЕ сохраняем активный клиент в ГЛОБАЛЬНОЙ памяти для доставки кода
            global _GLOBAL_AUTH_SESSIONS
            _GLOBAL_AUTH_SESSIONS[auth_key] = {
                'client': client,
                'phone_code_hash': phone_code_hash,
                'timestamp': int(time.time())
            }
            
            logger.info(f"Saved auth session to Redis AND global memory: {redis_key}")
            
        except Exception as e:
            logger.error(f"Error saving auth session: {e}")
    
    async def _get_auth_session(self, auth_key: str) -> Optional[Dict]:
        """Получение состояния авторизации из глобальной памяти или Redis"""
        try:
            global _GLOBAL_AUTH_SESSIONS
            
            # Сначала проверяем глобальную память (активный клиент)
            if auth_key in _GLOBAL_AUTH_SESSIONS:
                logger.info(f"Retrieved auth session from global memory: {auth_key}")
                return _GLOBAL_AUTH_SESSIONS[auth_key]
            
            # Если нет в памяти - пытаемся получить из Redis и восстановить
            redis_key = f"auth_session:{auth_key}"
            data = self.redis_client.get(redis_key)
            
            if data:
                auth_data = json.loads(data)
                logger.info(f"Retrieved auth session from Redis: {redis_key}")
                return auth_data
            else:
                logger.info(f"No auth session found in global memory or Redis: {auth_key}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting auth session: {e}")
            return None
    
    async def _delete_auth_session(self, auth_key: str) -> None:
        """Удаление состояния авторизации из Redis и глобальной памяти"""
        try:
            # Удаляем из Redis
            redis_key = f"auth_session:{auth_key}"
            self.redis_client.delete(redis_key)
            
            # Удаляем из глобальной памяти и отключаем клиент если есть
            global _GLOBAL_AUTH_SESSIONS
            if auth_key in _GLOBAL_AUTH_SESSIONS:
                if 'client' in _GLOBAL_AUTH_SESSIONS[auth_key]:
                    try:
                        await _GLOBAL_AUTH_SESSIONS[auth_key]['client'].disconnect()
                    except:
                        pass
                del _GLOBAL_AUTH_SESSIONS[auth_key]
            
            logger.info(f"Deleted auth session from Redis and global memory: {auth_key}")
        except Exception as e:
            logger.error(f"Error deleting auth session: {e}")
    
    async def _create_client_from_session(self, session_string: str) -> TelegramClient:
        """Создание клиента из сохраненной сессии"""
        api_id, api_hash = await self._get_api_credentials()
        session = StringSession(session_string)
        client = TelegramClient(session, api_id, api_hash)
        await client.connect()
        return client
    
    def _cleanup_old_auth_sessions(self) -> None:
        """Очистка старых auth sessions для предотвращения утечек памяти"""
        try:
            global _GLOBAL_AUTH_SESSIONS
            current_time = int(time.time())
            expired_keys = []
            
            for auth_key, auth_data in _GLOBAL_AUTH_SESSIONS.items():
                # Удаляем сессии старше 10 минут
                if current_time - auth_data.get('timestamp', 0) > 600:
                    expired_keys.append(auth_key)
            
            for key in expired_keys:
                if 'client' in _GLOBAL_AUTH_SESSIONS[key]:
                    try:
                        # НЕ используем await здесь так как это sync метод
                        # asyncio.create_task(_GLOBAL_AUTH_SESSIONS[key]['client'].disconnect())
                        pass  # Клиент отключится сам через timeout
                    except:
                        pass
                del _GLOBAL_AUTH_SESSIONS[key]
                logger.info(f"Cleaned up expired auth session: {key}")
                
        except Exception as e:
            logger.error(f"Error cleaning up auth sessions: {e}") 