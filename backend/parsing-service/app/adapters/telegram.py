"""
Telegram platform adapter for parsing channels and groups with Telethon.
"""

import asyncio
import logging
import os
import tempfile
from typing import List, Dict, Any, Optional
from datetime import datetime

from telethon import TelegramClient
from telethon.tl.types import (
    User, Channel, Chat, Message, 
    PeerUser, PeerChannel, PeerChat,
    MessageMediaPhoto, MessageMediaDocument
)
from telethon.errors import (
    FloodWaitError, SessionPasswordNeededError, 
    AuthKeyError, ChannelPrivateError, ChatAdminRequiredError,
    UserPrivacyRestrictedError, PeerFloodError
)
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.channels import GetFullChannelRequest

from .base import BasePlatformAdapter
from ..core.config import Platform
from ..models.parse_task import ParseTask
from ..models.parse_result import ParseResult

logger = logging.getLogger(__name__)


class TelegramAdapter(BasePlatformAdapter):
    """Telegram platform adapter for parsing channels and groups with Telethon."""
    
    def __init__(self):
        super().__init__(Platform.TELEGRAM)
        self.client = None
        self.api_id = None
        self.api_hash = None
        
    @property
    def platform_name(self) -> str:
        return "Telegram"
    
    async def authenticate(self, account_id: str, credentials: Dict[str, Any]) -> bool:
        """Authenticate with Telegram using credentials from integration-service."""
        try:
            # Получаем все данные от integration-service (НЕ из Vault!)
            session_id = credentials.get('session_id')
            self.api_id = credentials.get('api_id')
            self.api_hash = credentials.get('api_hash')  
            session_data = credentials.get('session_data')
            
            if not session_id:
                self.logger.error("No session_id provided by integration-service")
                return False
                
            if not self.api_id or not self.api_hash:
                self.logger.error("No API credentials provided by integration-service")
                return False
                
            if not session_data:
                self.logger.error(f"No session data provided for session {session_id}")
                return False
            
            self.logger.info(f"🔐 Using API credentials from integration-service: api_id={self.api_id}")
            
            # Получаем StringSession из данных integration-service  
            session_string = None
            
            if isinstance(session_data, dict):
                # Session_data из БД - это JSON объект с ключом "encrypted_session"
                if 'encrypted_session' in session_data:
                    # Декодируем base64 → получаем StringSession как строку
                    encrypted_session = session_data['encrypted_session']
                    try:
                        import base64
                        session_bytes = base64.b64decode(encrypted_session)
                        session_string = session_bytes.decode('utf-8')
                        self.logger.info(f"✅ Decoded StringSession from base64: {len(session_string)} chars")
                    except Exception as decode_error:
                        self.logger.error(f"❌ Failed to decode base64 session: {decode_error}")
                        session_string = encrypted_session
                else:
                    # Если JSON содержит другие данные сессии
                    self.logger.warning(f"⚠️ Unexpected session_data format: {list(session_data.keys())}")
                    session_string = None
            elif isinstance(session_data, str):
                # Если данные в base64 или уже строка
                try:
                    import base64
                    session_bytes = base64.b64decode(session_data)
                    session_string = session_bytes.decode('utf-8')
                except:
                    session_string = session_data
            
            if not session_string:
                self.logger.error("❌ Could not extract StringSession from session_data")
                return False
            
            self.logger.info(f"📱 Using StringSession directly (length: {len(session_string)})")
            
            # Initialize Telegram client with StringSession (НЕ файл!)
            from telethon.sessions import StringSession
            self.client = TelegramClient(
                session=StringSession(session_string),
                api_id=int(self.api_id),
                api_hash=self.api_hash,
                device_model="Content Factory Parser",
                system_version="1.0",
                app_version="1.0"
            )
            
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                self.logger.error("Session is not authorized")
                return False
            
            me = await self.client.get_me()
            self.logger.info(f"✅ Telegram authenticated for user {me.first_name} ({me.id}) using integration-service credentials")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Authentication failed: {e}")
            return False
    
    async def validate_targets(self, targets: List[str]) -> Dict[str, bool]:
        """Validate if Telegram targets exist and are accessible."""
        results = {}
        
        for target in targets:
            try:
                normalized_target = self.normalize_target(target)
                
                # Try to get entity info
                entity = await self.client.get_entity(normalized_target)
                
                if isinstance(entity, (Channel, Chat)):
                    results[target] = True
                    self.logger.info(f"✅ Validated target: {entity.title}")
                else:
                    results[target] = False
                    self.logger.warning(f"❌ Target is not a channel/group: {target}")
                    
            except (ChannelPrivateError, ChatAdminRequiredError):
                self.logger.warning(f"❌ Access denied to target '{target}'")
                results[target] = False
            except Exception as e:
                self.logger.warning(f"❌ Cannot validate target '{target}': {e}")
                results[target] = False
        
        return results
    
    async def parse_target(self, task: ParseTask, target: str, config: Dict[str, Any]):
        """Parse messages from a Telegram target with speed configuration support."""
        try:
            normalized_target = self.normalize_target(target)
            message_limit = config.get('message_limit', 10000)
            progress_callback = config.get('progress_callback')
            speed_config = config.get('speed_config')  # New: speed configuration
            
            if speed_config:
                self.logger.info(f"📥 Starting to parse {normalized_target} (USER LIMIT: {message_limit} users, SPEED: {speed_config.name})")
                self.logger.info(f"⚡ Speed settings: {speed_config.user_request_delay}s user delay, {speed_config.user_requests_per_minute} req/min")
            else:
                self.logger.info(f"📥 Starting to parse {normalized_target} (USER LIMIT: {message_limit} users, DEFAULT SPEED)")
            
            # Get entity (Channel/Group)
            entity = await self.client.get_entity(normalized_target)
            
            parsed_results = []
            
            if isinstance(entity, Channel):
                parsed_results = await self._parse_channel(task, entity, message_limit, progress_callback, speed_config)
            elif isinstance(entity, Chat):
                parsed_results = await self._parse_group(task, entity, message_limit, progress_callback, speed_config)
            else:
                raise ValueError(f"Unsupported entity type: {type(entity)}")
            
            self.logger.info(f"✅ Completed parsing {normalized_target}, returning {len(parsed_results)} results")
            return parsed_results
            
        except Exception as e:
            self.logger.error(f"❌ Failed to parse {target}: {e}")
            raise
    
    async def _parse_channel(self, task: ParseTask, channel: Channel, message_limit: int, progress_callback=None, speed_config=None):
        """Parse users from a Telegram channel by collecting commenters from posts."""
        self.logger.info(f"📱 Parsing channel users: {channel.title} (USER LIMIT: {message_limit} users)")
        
        # Apply speed configuration defaults if not provided
        if speed_config:
            message_delay = speed_config.message_delay
            user_request_delay = speed_config.user_request_delay
            batch_size = speed_config.batch_size
            self.logger.info(f"⚡ Channel parsing speed: {message_delay}s msg delay, {user_request_delay}s user delay, batch {batch_size}")
        else:
            # Default speed settings (medium)
            message_delay = 0.8
            user_request_delay = 1.5
            batch_size = 25
            self.logger.info("⚡ Using default speed settings")
        
        unique_users = {}  # user_id -> user_data
        processed_messages = 0
        found_commenters = 0
        request_count = 0  # Track requests for batch processing
        
        # Get recent messages to find users who commented
        # Use larger message limit since we're limiting by USERS, not messages
        message_search_limit = max(message_limit * 10, 1000)  # Search more messages to find enough users
        self.logger.info(f"📝 Will search through {message_search_limit} messages to find {message_limit} users")
        async for message in self.client.iter_messages(channel, limit=message_search_limit):
            if not isinstance(message, Message):
                continue
                
            # Check if we already reached user limit before processing more messages
            if found_commenters >= message_limit:
                self.logger.info(f"🛑 USER LIMIT REACHED: {found_commenters}/{message_limit} - stopping message iteration")
                break
                
            processed_messages += 1
            
            # Check if message has comments/replies (only for channels with comments enabled)
            if hasattr(message, 'replies') and message.replies and message.replies.replies > 0:
                try:
                    # Rate limiting: speed-configurable delay between message requests
                    await asyncio.sleep(message_delay)
                    
                    # Get comments/replies for this message
                    comment_count = 0
                    async for reply in self.client.iter_messages(
                        channel, 
                        reply_to=message.id,
                        limit=50  # Limit comments per post
                    ):
                        if reply.from_id and isinstance(reply.from_id, PeerUser):
                            user_id = reply.from_id.user_id
                            
                            # Skip if we already have this user
                            if user_id in unique_users:
                                continue
                            
                            try:
                                user = await self.client.get_entity(reply.from_id)
                                user_data = await self._extract_user_data(task, user, channel, "commenter")
                                unique_users[user_id] = user_data
                                found_commenters += 1
                                comment_count += 1
                                request_count += 1
                                
                                # 🔥 ПРОВЕРКА ЛИМИТА ПОЛЬЗОВАТЕЛЕЙ
                                if found_commenters >= message_limit:
                                    self.logger.info(f"🛑 LIMIT REACHED: {found_commenters}/{message_limit} users found - STOPPING CHANNEL PARSING")
                                    channel_metadata = await self._extract_channel_metadata(task, channel)
                                    final_results = [channel_metadata] + list(unique_users.values())
                                    self.logger.info(f"✅ Returning {len(final_results)} results due to user limit")
                                    return final_results
                                
                                # Calculate progress update frequency (every 5% of message_limit)
                                progress_step = max(1, int(message_limit * 0.05))
                                if found_commenters % progress_step == 0:
                                    self.logger.info(f"Found {found_commenters} unique commenters...")
                                    # Update progress if callback provided
                                    if progress_callback:
                                        try:
                                            await progress_callback(found_commenters, message_limit)
                                        except Exception as e:
                                            self.logger.debug(f"Progress callback error: {e}")
                                
                                # Speed-configurable rate limiting for user requests
                                if request_count % batch_size == 0:
                                    await asyncio.sleep(user_request_delay)
                                    
                            except FloodWaitError as e:
                                self.logger.warning(f"FloodWait {e.seconds}s - pausing...")
                                try:
                                    # Защищенное ожидание FloodWait от отмены
                                    await asyncio.sleep(e.seconds + 1)
                                except asyncio.CancelledError:
                                    self.logger.warning(f"⚠️ FloodWait cancelled during {e.seconds}s wait")
                                    raise
                            except Exception as e:
                                self.logger.debug(f"Could not get commenter data for user {user_id}: {e}")
                
                except FloodWaitError as e:
                    self.logger.warning(f"FloodWait {e.seconds}s while getting replies for message {message.id}")
                    try:
                        await asyncio.sleep(e.seconds + 1)
                    except asyncio.CancelledError:
                        self.logger.warning(f"⚠️ FloodWait cancelled during {e.seconds}s wait for message {message.id}")
                        raise
                except Exception as e:
                    self.logger.debug(f"Could not get replies for message {message.id}: {e}")
            
            # Also collect message authors (if not anonymous channel)
            if message.from_id and isinstance(message.from_id, PeerUser):
                user_id = message.from_id.user_id
                if user_id not in unique_users:
                    try:
                        user = await self.client.get_entity(message.from_id)
                        user_data = await self._extract_user_data(task, user, channel, "author")
                        unique_users[user_id] = user_data
                        found_commenters += 1
                        
                        # 🔥 ПРОВЕРКА ЛИМИТА ПОЛЬЗОВАТЕЛЕЙ
                        if found_commenters >= message_limit:
                            self.logger.info(f"🛑 LIMIT REACHED: {found_commenters}/{message_limit} users found - STOPPING CHANNEL PARSING")
                            channel_metadata = await self._extract_channel_metadata(task, channel)
                            final_results = [channel_metadata] + list(unique_users.values())
                            self.logger.info(f"✅ Returning {len(final_results)} results due to user limit")
                            return final_results
                        
                    except Exception as e:
                        self.logger.debug(f"Could not get author data for user {user_id}: {e}")
            
            if processed_messages % 50 == 0:
                self.logger.info(f"Processed {processed_messages} messages, found {len(unique_users)} unique users...")
        
        # Add channel metadata as first result
        channel_metadata = await self._extract_channel_metadata(task, channel)
        
        parsed_results = [channel_metadata] + list(unique_users.values())
        self.logger.info(f"📊 Channel parsing complete: {processed_messages} messages processed, {len(unique_users)} unique users found")
        return parsed_results
    
    async def _parse_group(self, task: ParseTask, chat: Chat, message_limit: int, progress_callback=None, speed_config=None):
        """Parse users from a Telegram group by collecting all participants."""
        self.logger.info(f"👥 Parsing group users: {chat.title} (USER LIMIT: {message_limit} users)")
        
        # Apply speed configuration defaults if not provided
        if speed_config:
            message_delay = speed_config.message_delay
            user_request_delay = speed_config.user_request_delay
            batch_size = speed_config.batch_size
            self.logger.info(f"⚡ Group parsing speed: {message_delay}s msg delay, {user_request_delay}s user delay, batch {batch_size}")
        else:
            # Default speed settings (medium)
            message_delay = 0.8
            user_request_delay = 1.5
            batch_size = 25
            self.logger.info("⚡ Using default speed settings")
        
        unique_users = {}  # user_id -> user_data
        request_count = 0  # Track requests for batch processing
        
        # Parse group participants (primary focus)
        participant_count = 0
        try:
            async for participant in self.client.iter_participants(chat):
                if isinstance(participant, User):
                    user_id = participant.id
                    
                    # Skip if we already have this user
                    if user_id in unique_users:
                        continue
                    
                    try:
                        user_data = await self._extract_user_data(task, participant, chat, "participant")
                        unique_users[user_id] = user_data
                        participant_count += 1
                        request_count += 1
                        
                        # 🔥 ПРОВЕРКА ЛИМИТА ПОЛЬЗОВАТЕЛЕЙ
                        if participant_count >= message_limit:
                            self.logger.info(f"🛑 LIMIT REACHED: {participant_count}/{message_limit} users found - STOPPING GROUP PARSING")
                            group_metadata = await self._extract_group_metadata(task, chat)
                            final_results = [group_metadata] + list(unique_users.values())
                            self.logger.info(f"✅ Returning {len(final_results)} results due to user limit")
                            return final_results
                        
                        # Calculate progress update frequency (every 5% of message_limit)
                        progress_step = max(1, int(message_limit * 0.05))
                        if participant_count % progress_step == 0:
                            self.logger.info(f"Processed {participant_count} participants...")
                            # Update progress if callback provided
                            if progress_callback:
                                try:
                                    await progress_callback(participant_count, message_limit)
                                except Exception as e:
                                    self.logger.debug(f"Progress callback error: {e}")
                        
                        # Speed-configurable rate limiting for large groups
                        if request_count % batch_size == 0:
                            await asyncio.sleep(user_request_delay)
                    
                    except FloodWaitError as e:
                        self.logger.warning(f"FloodWait {e.seconds}s while processing participant {user_id}")
                        try:
                            await asyncio.sleep(e.seconds + 1)
                        except asyncio.CancelledError:
                            self.logger.warning(f"⚠️ FloodWait cancelled during {e.seconds}s wait for participant {user_id}")
                            raise
                    except Exception as e:
                        self.logger.debug(f"Could not process participant {user_id}: {e}")
        
        except ChatAdminRequiredError:
            self.logger.warning("Cannot access participant list - admin rights required")
            
            # Fallback: collect users from recent messages
            self.logger.info("Fallback: collecting users from recent messages...")
            message_count = 0
            async for message in self.client.iter_messages(chat, limit=message_limit):
                if not isinstance(message, Message):
                    continue
                    
                # Check if we already reached user limit before processing more messages
                if participant_count >= message_limit:
                    self.logger.info(f"🛑 USER LIMIT REACHED: {participant_count}/{message_limit} - stopping fallback message iteration")
                    break
                    
                message_count += 1
                
                # Get message author
                if message.from_id and isinstance(message.from_id, PeerUser):
                    user_id = message.from_id.user_id
                    if user_id not in unique_users:
                        try:
                            user = await self.client.get_entity(message.from_id)
                            user_data = await self._extract_user_data(task, user, chat, "message_author")
                            unique_users[user_id] = user_data
                            participant_count += 1
                            
                            # 🔥 ПРОВЕРКА ЛИМИТА ПОЛЬЗОВАТЕЛЕЙ
                            if participant_count >= message_limit:
                                self.logger.info(f"🛑 LIMIT REACHED: {participant_count}/{message_limit} users found - STOPPING GROUP PARSING (fallback mode)")
                                group_metadata = await self._extract_group_metadata(task, chat)
                                final_results = [group_metadata] + list(unique_users.values())
                                self.logger.info(f"✅ Returning {len(final_results)} results due to user limit")
                                return final_results
                        except FloodWaitError as e:
                            self.logger.warning(f"FloodWait {e.seconds}s while getting message author {user_id}")
                            try:
                                await asyncio.sleep(e.seconds + 1)
                            except asyncio.CancelledError:
                                self.logger.warning(f"⚠️ FloodWait cancelled during {e.seconds}s wait for message author {user_id}")
                                raise
                        except Exception as e:
                            self.logger.debug(f"Could not get message author data for user {user_id}: {e}")
                
                if message_count % 100 == 0:
                    self.logger.info(f"Processed {message_count} messages, found {len(unique_users)} unique users...")
        
        # Add group metadata as first result
        group_metadata = await self._extract_group_metadata(task, chat)
        
        parsed_results = [group_metadata] + list(unique_users.values())
        self.logger.info(f"📊 Group parsing complete: {len(unique_users)} unique users found")
        return parsed_results
    
    async def _get_user_phone(self, user: User) -> Optional[str]:
        """Get user's phone number if accessible."""
        try:
            # Check if phone is already available in user object
            if hasattr(user, 'phone') and user.phone:
                return f"+{user.phone}"
            
            # Try to get full user info (may fail due to privacy settings)
            try:
                full_user = await self.client(GetFullUserRequest(user))
                if hasattr(full_user.user, 'phone') and full_user.user.phone:
                    return f"+{full_user.user.phone}"
            except FloodWaitError as e:
                self.logger.warning(f"FloodWait {e.seconds}s while getting full user info for {user.id}")
                try:
                    await asyncio.sleep(e.seconds + 1)
                    # Retry after FloodWait
                    full_user = await self.client(GetFullUserRequest(user))
                    if hasattr(full_user.user, 'phone') and full_user.user.phone:
                        return f"+{full_user.user.phone}"
                except asyncio.CancelledError:
                    self.logger.warning(f"⚠️ FloodWait cancelled during {e.seconds}s wait for user {user.id}")
                    return None
                except Exception:
                    self.logger.debug(f"Could not get phone after FloodWait retry for user {user.id}")
                    return None
            except Exception as full_user_error:
                self.logger.debug(f"Could not get full user info for {user.id}: {full_user_error}")
            
            # Check if user has contact info in mutual contacts
            try:
                if hasattr(user, 'contact') and user.contact:
                    return f"+{user.phone}" if user.phone else None
            except Exception:
                pass
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Could not get phone for user {user.id}: {e}")
            return None
    
    async def _extract_user_data(self, task: ParseTask, user: User, entity, user_type: str) -> Dict[str, Any]:
        """Extract user data from a Telegram user."""
        from datetime import datetime
        
        # Get user's phone number
        user_phone = await self._get_user_phone(user)
        
        # Construct full name
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        if not full_name:
            full_name = user.username or f"User {user.id}"
        
        # Create user description based on type
        if user_type == "participant":
            content_text = f"Group participant: {full_name}"
        elif user_type == "commenter":
            content_text = f"Channel commenter: {full_name}"
        elif user_type == "author":
            content_text = f"Post author: {full_name}"
        elif user_type == "message_author":
            content_text = f"Message author: {full_name}"
        else:
            content_text = f"User: {full_name}"
        
        # Use naive UTC datetime for database compatibility
        content_created_at = datetime.utcnow()
        
        # Convert user.to_dict() and sanitize datetime objects
        raw_data = self._sanitize_datetime_objects(user.to_dict())
        
        return {
            'task_id': task.id,
            'platform': Platform.TELEGRAM,
            'source_id': str(entity.id),
            'source_name': getattr(entity, 'title', getattr(entity, 'username', 'Unknown')),
            'source_type': 'channel' if isinstance(entity, Channel) else 'group',
            'content_id': f"user_{user.id}",
            'content_type': 'user',  # Changed from 'message' to 'user'
            'content_text': content_text,
            'author_id': str(user.id),
            'author_username': user.username,
            'author_name': full_name,
            'author_phone': user_phone,
            'content_created_at': content_created_at,
            'views_count': 0,
            'has_media': False,
            'media_count': 0,
            'media_types': [],
            'is_forwarded': False,
            'is_reply': False,
            'platform_data': {
                'user_id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_bot': user.bot,
                'is_verified': user.verified,
                'is_premium': getattr(user, 'premium', False),
                'user_type': user_type,
                'phone': user_phone,
                'language_code': getattr(user, 'lang_code', None),
                'chat_id': entity.id,
                'chat_title': getattr(entity, 'title', 'Unknown')
            },
            'raw_data': raw_data
        }
    
    async def _extract_channel_metadata(self, task: ParseTask, channel: Channel) -> Dict[str, Any]:
        """Extract metadata about the channel itself."""
        from datetime import datetime
        
        try:
            # Get full channel info
            full_channel = await self.client(GetFullChannelRequest(channel))
            participants_count = getattr(full_channel.full_chat, 'participants_count', 0)
            
            return {
                'task_id': task.id,
                'platform': Platform.TELEGRAM,
                'source_id': str(channel.id),
                'source_name': channel.title or channel.username or 'Unknown Channel',
                'source_type': 'channel',
                'content_id': f"channel_{channel.id}",
                'content_type': 'channel_metadata',
                'content_text': f"Channel metadata: {channel.title}",
                'author_id': None,
                'author_username': channel.username,
                'author_name': f"Channel: {channel.title}",
                'author_phone': None,
                'content_created_at': datetime.utcnow(),
                'views_count': 0,
                'has_media': False,
                'media_count': 0,
                'media_types': [],
                'platform_data': self._sanitize_datetime_objects({
                    'channel_id': channel.id,
                    'username': channel.username,
                    'title': channel.title,
                    'participants_count': participants_count,
                    'is_verified': getattr(channel, 'verified', False),
                    'is_broadcast': getattr(channel, 'broadcast', False),
                    'is_megagroup': getattr(channel, 'megagroup', False),
                    'description': getattr(full_channel.full_chat, 'about', ''),
                    'date_created': getattr(channel, 'date', None)
                }),
                'raw_data': self._sanitize_datetime_objects(channel.to_dict())
            }
        except Exception as e:
            self.logger.error(f"Could not get channel metadata: {e}")
            return {
                'task_id': task.id,
                'platform': Platform.TELEGRAM,
                'source_id': str(channel.id),
                'source_name': channel.title or 'Unknown Channel',
                'source_type': 'channel',
                'content_id': f"channel_{channel.id}",
                'content_type': 'channel_metadata',
                'content_text': f"Channel metadata: {channel.title}",
                'content_created_at': datetime.utcnow(),
                'platform_data': {'error': str(e)},
                'raw_data': {}
            }
    
    async def _extract_group_metadata(self, task: ParseTask, chat: Chat) -> Dict[str, Any]:
        """Extract metadata about the group itself.""" 
        from datetime import datetime
        
        try:
            # Get basic group info
            participants_count = getattr(chat, 'participants_count', 0)
            
            return {
                'task_id': task.id,
                'platform': Platform.TELEGRAM,
                'source_id': str(chat.id),
                'source_name': chat.title or 'Unknown Group',
                'source_type': 'group',
                'content_id': f"group_{chat.id}",
                'content_type': 'group_metadata',
                'content_text': f"Group metadata: {chat.title}",
                'author_id': None,
                'author_username': None,
                'author_name': f"Group: {chat.title}",
                'author_phone': None,
                'content_created_at': datetime.utcnow(),
                'views_count': 0,
                'has_media': False,
                'media_count': 0,
                'media_types': [],
                'platform_data': self._sanitize_datetime_objects({
                    'chat_id': chat.id,
                    'title': chat.title,
                    'participants_count': participants_count,
                    'date_created': getattr(chat, 'date', None),
                    'is_creator': getattr(chat, 'creator', False),
                    'admin_rights': getattr(chat, 'admin_rights', None)
                }),
                'raw_data': self._sanitize_datetime_objects(chat.to_dict())
            }
        except Exception as e:
            self.logger.error(f"Could not get group metadata: {e}")
            return {
                'task_id': task.id,
                'platform': Platform.TELEGRAM,
                'source_id': str(chat.id),
                'source_name': chat.title or 'Unknown Group',
                'source_type': 'group',
                'content_id': f"group_{chat.id}",
                'content_type': 'group_metadata',
                'content_text': f"Group metadata: {chat.title}",
                'content_created_at': datetime.utcnow(),
                'platform_data': {'error': str(e)},
                'raw_data': {}
            }

    def _sanitize_datetime_objects(self, obj):
        """Recursively convert datetime and bytes objects for JSON serialization."""
        from datetime import datetime
        import base64
        
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, bytes):
            # Convert bytes to base64 string for JSON serialization
            try:
                return base64.b64encode(obj).decode('utf-8')
            except Exception:
                # If base64 encoding fails, convert to hex string
                return obj.hex()
        elif isinstance(obj, dict):
            return {key: self._sanitize_datetime_objects(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._sanitize_datetime_objects(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(self._sanitize_datetime_objects(item) for item in obj)
        else:
            return obj
    
    def _get_media_types(self, message: Message) -> List[str]:
        """Get media types from message."""
        if not message.media:
            return []
            
        media_types = []
        if isinstance(message.media, MessageMediaPhoto):
            media_types.append('photo')
        elif isinstance(message.media, MessageMediaDocument):
            if message.media.document:
                mime_type = message.media.document.mime_type
                if mime_type.startswith('video/'):
                    media_types.append('video')
                elif mime_type.startswith('audio/'):
                    media_types.append('audio')
                else:
                    media_types.append('document')
        
        return media_types
    
    async def cleanup(self):
        """Clean up Telegram client with proper exception handling."""
        try:
            if self.client:
                # Безопасное отключение клиента с таймаутом
                try:
                    # Принудительно отменяем все pending операции
                    if self.client.is_connected():
                        await asyncio.wait_for(self.client.disconnect(), timeout=5.0)
                except asyncio.TimeoutError:
                    self.logger.warning("⚠️ Telegram client disconnect timeout, forcing cleanup")
                except (asyncio.CancelledError, GeneratorExit):
                    self.logger.warning("⚠️ Telegram client disconnect cancelled")
                except Exception as disconnect_error:
                    self.logger.warning(f"⚠️ Telegram client disconnect error: {disconnect_error}")
                finally:
                    # Принудительно очищаем клиент
                    self.client = None
                
            self.logger.info("🗑️ Telegram adapter cleaned up")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            # Принудительно очищаем клиент даже при ошибке
            self.client = None
    
    def normalize_target(self, target: str) -> str:
        """Normalize Telegram target format."""
        target = target.strip()
        
        # Remove various prefixes
        if target.startswith('https://t.me/'):
            target = target[13:]
        elif target.startswith('http://t.me/'):
            target = target[12:]
        elif target.startswith('t.me/'):
            target = target[5:]
        elif target.startswith('@'):
            target = target[1:]
        
        # Remove any additional parameters
        if '?' in target:
            target = target.split('?')[0]
        
        return target
    
    async def search_communities(self, query: str, offset: int = 0, limit: int = 10, **kwargs) -> Dict[str, Any]:
        """
        Search for Telegram communities (channels/groups) by keywords.
        
        Filters: Only open channels with comments enabled OR open groups
        Sorting: By member count descending (largest first)
        """
        self.logger.info(f"🔍 Searching Telegram communities for query: '{query}' (offset={offset}, limit={limit})")
        
        if not self.client:
            raise Exception("Telegram client not authenticated")
        
        try:
            from telethon.tl.functions.contacts import SearchRequest
            from telethon.tl.functions.messages import SearchGlobalRequest
            from telethon.tl.types import Channel, Chat
            
            results = []
            search_results = []
            
            # Generate search query variations for better results
            search_queries = [query]
            
            # Add transliteration variations if query contains cyrillic
            if any(ord(c) > 127 for c in query):
                # Add English transliteration attempts
                transliterations = self._generate_transliterations(query)
                search_queries.extend(transliterations)
            
            # Add common suffixes for sports/topics
            base_suffixes = ['_channel', '_official', '_news', '_chat']
            for suffix in base_suffixes:
                search_queries.append(f"{query}{suffix}")
            
            self.logger.info(f"🔍 Searching with {len(search_queries)} query variations: {search_queries[:3]}...")
            
            # Try different search approaches to get more results
            for search_query in search_queries[:5]:  # Limit to avoid too many API calls
                search_methods = [
                    # Method 1: Global search for channels
                    self._search_global_channels(search_query),
                    # Method 2: Search in dialogs  
                    self._search_dialogs(search_query),
                    # Method 3: Global search (newer API)
                    self._search_global_new(search_query),
                ]
                
                for search_method in search_methods:
                    try:
                        method_results = await search_method
                        search_results.extend(method_results)
                        
                        # Break if we have enough results to avoid rate limiting
                        if len(search_results) > 100:
                            break
                    except Exception as e:
                        self.logger.debug(f"Search method failed for '{search_query}': {e}")
                        continue
                
                # Break if we have enough results
                if len(search_results) > 100:
                    break
            
            # Remove duplicates by username/id
            unique_results = {}
            for result in search_results:
                key = result.get('username') or result.get('platform_id')
                if key and key not in unique_results:
                    unique_results[key] = result
            
            all_results = list(unique_results.values())
            
            # Sort by member count descending (largest first)
            all_results.sort(key=lambda x: x.get('members_count', 0), reverse=True)
            
            # Apply pagination
            paginated_results = all_results[offset:offset + limit]
            has_more = len(all_results) > offset + limit
            
            self.logger.info(f"✅ Found {len(all_results)} total communities, returning {len(paginated_results)} (has_more: {has_more})")
            
            return {
                'results': paginated_results,
                'has_more': has_more,
                'total_found': len(all_results)
            }
            
        except Exception as e:
            self.logger.error(f"❌ Failed to search Telegram communities: {e}")
            raise
    
    async def _search_global_channels(self, query: str) -> List[Dict[str, Any]]:
        """Search for global channels using SearchRequest."""
        try:
            from telethon.tl.functions.contacts import SearchRequest
            from telethon.tl.types import Channel, Chat
            
            # Use contacts search for public entities
            search_result = await self.client(SearchRequest(
                q=query,
                limit=200  # Increased from 50 to get more results
            ))
            
            results = []
            for user in search_result.users:
                # Skip regular users, only process channels/groups
                continue
                
            for chat in search_result.chats:
                if isinstance(chat, (Channel, Chat)):
                    community_data = await self._extract_community_data(chat)
                    if community_data:
                        results.append(community_data)
            
            return results
            
        except Exception as e:
            self.logger.debug(f"Global search failed: {e}")
            return []
    
    async def _search_dialogs(self, query: str) -> List[Dict[str, Any]]:
        """Search through user's dialogs for matching communities."""
        try:
            from telethon.tl.types import Channel, Chat
            
            results = []
            query_lower = query.lower()
            
            # Get user's dialogs and filter by query - increased limit
            async for dialog in self.client.iter_dialogs(limit=500):
                entity = dialog.entity
                
                if isinstance(entity, (Channel, Chat)):
                    # Check if title or username matches query
                    title = getattr(entity, 'title', '').lower()
                    username = getattr(entity, 'username', '').lower()
                    
                    if (query_lower in title or 
                        query_lower in username or
                        (hasattr(entity, 'title') and any(word in title for word in query_lower.split()))):
                        
                        community_data = await self._extract_community_data(entity)
                        if community_data:
                            results.append(community_data)
            
            return results
            
        except Exception as e:
            self.logger.debug(f"Dialog search failed: {e}")
            return []
    
    async def _search_global_new(self, query: str) -> List[Dict[str, Any]]:
        """Search using SearchGlobalRequest for broader results."""
        try:
            from telethon.tl.functions.messages import SearchGlobalRequest
            from telethon.tl.types import Channel, Chat, InputMessagesFilterEmpty
            
            # Use global search
            search_result = await self.client(SearchGlobalRequest(
                q=query,
                filter=InputMessagesFilterEmpty(),  # No filter, get all types
                min_date=None,
                max_date=None,
                offset_rate=0,
                offset_peer=None,
                offset_id=0,
                limit=100
            ))
            
            results = []
            
            # Process found chats
            for chat in search_result.chats:
                if isinstance(chat, (Channel, Chat)):
                    community_data = await self._extract_community_data(chat)
                    if community_data:
                        results.append(community_data)
            
            return results
            
        except Exception as e:
            self.logger.debug(f"Global new search failed: {e}")
            return []
    
    def _generate_transliterations(self, query: str) -> List[str]:
        """Generate transliteration variations for Cyrillic text."""
        try:
            # Basic cyrillic to latin mapping for common letters
            cyrillic_to_latin = {
                'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
                'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
                'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
                'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
                'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
            }
            
            transliterations = []
            query_lower = query.lower()
            
            # Full transliteration
            transliterated = ''
            for char in query_lower:
                transliterated += cyrillic_to_latin.get(char, char)
            
            if transliterated != query_lower:
                transliterations.append(transliterated)
            
            # Common specific mappings for football/sports
            sport_mappings = {
                'футбол': ['football', 'soccer', 'futbol'],
                'хоккей': ['hockey'],
                'баскетбол': ['basketball'],
                'теннис': ['tennis'],
                'волейбол': ['volleyball']
            }
            
            for cyrillic, latin_variants in sport_mappings.items():
                if cyrillic in query_lower:
                    transliterations.extend(latin_variants)
            
            return transliterations
            
        except Exception as e:
            self.logger.debug(f"Transliteration failed: {e}")
            return []
    
    async def _extract_community_data(self, entity) -> Optional[Dict[str, Any]]:
        """Extract community data from Telegram entity with filtering."""
        try:
            from telethon.tl.types import Channel, Chat
            from telethon.tl.functions.channels import GetFullChannelRequest
            from telethon.tl.functions.messages import GetFullChatRequest
            
            if not isinstance(entity, (Channel, Chat)):
                return None
            
            # Basic entity info
            title = getattr(entity, 'title', 'Unnamed')
            username = getattr(entity, 'username', None)
            entity_id = getattr(entity, 'id', None)
            
            if not entity_id:
                return None
            
            # Apply filters - only open communities per requirements
            if isinstance(entity, Channel):
                # Skip private/restricted channels - must be open
                if getattr(entity, 'restricted', False):
                    self.logger.debug(f"Skipping restricted channel: {title}")
                    return None
                
                # Check if it's a megagroup (open group) or broadcast channel
                is_megagroup = getattr(entity, 'megagroup', False)
                is_broadcast = getattr(entity, 'broadcast', False)
                
                if is_broadcast and not is_megagroup:
                    # This is a broadcast channel - MUST have comments enabled
                    try:
                        full_channel = await self.client(GetFullChannelRequest(entity))
                        
                        # Check multiple ways for comments:
                        # 1. Has linked discussion group
                        has_discussion = (hasattr(full_channel.full_chat, 'linked_chat_id') and 
                                        full_channel.full_chat.linked_chat_id)
                        
                        # 2. Check if comments are not disabled in settings
                        comments_disabled = getattr(full_channel.full_chat, 'can_view_participants', True) == False
                        
                        if not has_discussion and comments_disabled:
                            self.logger.debug(f"Skipping broadcast channel {title} - no comments enabled")
                            return None
                        
                        self.logger.debug(f"✅ Broadcast channel {title} has comments enabled")
                        
                    except Exception as e:
                        # If we can't check comments, skip to be safe
                        self.logger.debug(f"Skipping channel {title} - can't verify comments: {e}")
                        return None
                elif is_megagroup:
                    # Megagroup (supergroup) - these are fine, they're essentially large groups
                    self.logger.debug(f"✅ Found megagroup: {title}")
                else:
                    # Unknown channel type
                    self.logger.debug(f"Skipping unknown channel type: {title}")
                    return None
                
                # Get detailed channel info
                try:
                    full_channel = await self.client(GetFullChannelRequest(entity))
                    participants_count = getattr(full_channel.full_chat, 'participants_count', 0)
                    about = getattr(full_channel.full_chat, 'about', '')
                except:
                    participants_count = 0
                    about = ''
                
            elif isinstance(entity, Chat):
                # Group filtering - skip private groups
                if hasattr(entity, 'access_hash') and not entity.access_hash:
                    return None
                
                # Get detailed chat info
                try:
                    full_chat = await self.client(GetFullChatRequest(entity.id))
                    participants_count = getattr(full_chat.full_chat, 'participants_count', 0)
                    about = getattr(full_chat.full_chat, 'about', '')
                except:
                    participants_count = getattr(entity, 'participants_count', 0)
                    about = ''
            
            # Generate community link
            if username:
                link = f"https://t.me/{username}"
            else:
                # For private groups/channels without username, use invite link format
                link = f"https://t.me/c/{entity_id}"
            
            community_data = {
                'platform': 'telegram',
                'platform_id': str(entity_id),
                'title': title,
                'username': username,
                'description': about[:200] if about else None,  # Limit description length
                'members_count': participants_count,
                'link': link,
                'platform_specific_data': {
                    'entity_type': 'channel' if isinstance(entity, Channel) else 'group',
                    'is_megagroup': getattr(entity, 'megagroup', False),
                    'is_broadcast': getattr(entity, 'broadcast', False),
                    'verified': getattr(entity, 'verified', False),
                    'restricted': getattr(entity, 'restricted', False)
                }
            }
            
            # Additional filtering - only include communities with decent member count
            if participants_count < 10:  # Skip very small communities
                self.logger.debug(f"Skipping {title} - too few members ({participants_count})")
                return None
            
            self.logger.debug(f"✅ Found community: {title} (@{username}) - {participants_count} members")
            return community_data
            
        except Exception as e:
            self.logger.debug(f"Failed to extract community data: {e}")
            return None 