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
        """Parse messages from a Telegram target."""
        try:
            normalized_target = self.normalize_target(target)
            message_limit = config.get('message_limit', 10000)
            
            self.logger.info(f"📥 Starting to parse {normalized_target} (limit: {message_limit})")
            
            # Get entity (Channel/Group)
            entity = await self.client.get_entity(normalized_target)
            
            parsed_results = []
            
            if isinstance(entity, Channel):
                parsed_results = await self._parse_channel(task, entity, message_limit)
            elif isinstance(entity, Chat):
                parsed_results = await self._parse_group(task, entity, message_limit)
            else:
                raise ValueError(f"Unsupported entity type: {type(entity)}")
            
            self.logger.info(f"✅ Completed parsing {normalized_target}, returning {len(parsed_results)} results")
            return parsed_results
            
        except Exception as e:
            self.logger.error(f"❌ Failed to parse {target}: {e}")
            raise
    
    async def _parse_channel(self, task: ParseTask, channel: Channel, message_limit: int):
        """Parse users from a Telegram channel by collecting commenters from posts."""
        self.logger.info(f"📱 Parsing channel users: {channel.title}")
        
        unique_users = {}  # user_id -> user_data
        processed_messages = 0
        found_commenters = 0
        
        # Get recent messages to find users who commented
        async for message in self.client.iter_messages(channel, limit=message_limit):
            if not isinstance(message, Message):
                continue
                
            processed_messages += 1
            
            # Check if message has comments/replies (only for channels with comments enabled)
            if hasattr(message, 'replies') and message.replies and message.replies.replies > 0:
                try:
                    # Rate limiting: small delay between requests
                    await asyncio.sleep(0.1)
                    
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
                                
                                if found_commenters % 10 == 0:
                                    self.logger.info(f"Found {found_commenters} unique commenters...")
                                
                                # Rate limiting for user requests
                                if comment_count % 5 == 0:
                                    await asyncio.sleep(0.5)
                                    
                            except FloodWaitError as e:
                                self.logger.warning(f"FloodWait {e.seconds}s - pausing...")
                                await asyncio.sleep(e.seconds + 1)
                            except Exception as e:
                                self.logger.debug(f"Could not get commenter data for user {user_id}: {e}")
                
                except FloodWaitError as e:
                    self.logger.warning(f"FloodWait {e.seconds}s while getting replies for message {message.id}")
                    await asyncio.sleep(e.seconds + 1)
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
                    except Exception as e:
                        self.logger.debug(f"Could not get author data for user {user_id}: {e}")
            
            if processed_messages % 50 == 0:
                self.logger.info(f"Processed {processed_messages} messages, found {len(unique_users)} unique users...")
        
        # Add channel metadata as first result
        channel_metadata = await self._extract_channel_metadata(task, channel)
        
        parsed_results = [channel_metadata] + list(unique_users.values())
        self.logger.info(f"📊 Channel parsing complete: {processed_messages} messages processed, {len(unique_users)} unique users found")
        return parsed_results
    
    async def _parse_group(self, task: ParseTask, chat: Chat, message_limit: int):
        """Parse users from a Telegram group by collecting all participants."""
        self.logger.info(f"👥 Parsing group users: {chat.title}")
        
        unique_users = {}  # user_id -> user_data
        
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
                        
                        if participant_count % 50 == 0:
                            self.logger.info(f"Processed {participant_count} participants...")
                            # Rate limiting for large groups
                            await asyncio.sleep(0.1)
                    
                    except FloodWaitError as e:
                        self.logger.warning(f"FloodWait {e.seconds}s while processing participant {user_id}")
                        await asyncio.sleep(e.seconds + 1)
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
                        except FloodWaitError as e:
                            self.logger.warning(f"FloodWait {e.seconds}s while getting message author {user_id}")
                            await asyncio.sleep(e.seconds + 1)
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
            'raw_data': user.to_dict()
        }
    

    
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
        """Clean up Telegram client."""
        try:
            if self.client:
                await self.client.disconnect()
                self.client = None
                
            self.logger.info("🗑️ Telegram adapter cleaned up")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
    
    def normalize_target(self, target: str) -> str:
        """Normalize Telegram target identifier."""
        target = target.strip()
        
        # Remove t.me/ prefix if present
        if target.startswith('https://t.me/'):
            target = target.replace('https://t.me/', '')
        elif target.startswith('t.me/'):
            target = target.replace('t.me/', '')
        
        # Keep @ prefix for Telegram
        if not target.startswith('@') and not target.isdigit():
            target = '@' + target
        
        return target 