"""
Real Telegram platform adapter with Telethon implementation for phone number parsing.
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
    AuthKeyError, ChannelPrivateError, ChatAdminRequiredError
)
from telethon.tl.functions.users import GetFullUserRequest

from .base import BasePlatformAdapter
from ..core.config import Platform
from ..core.vault import get_vault_client
from ..models.parse_task import ParseTask

logger = logging.getLogger(__name__)


class TelegramRealAdapter(BasePlatformAdapter):
    """Real Telegram platform adapter with Telethon for phone number parsing."""
    
    def __init__(self):
        super().__init__(Platform.TELEGRAM)
        self.client = None
        self.session_file_path = None
        self.vault_client = get_vault_client()
        self.api_id = None
        self.api_hash = None
        
    @property
    def platform_name(self) -> str:
        return "Telegram"
    
    async def authenticate(self, account_id: str, credentials: Dict[str, Any]) -> bool:
        """Authenticate with Telegram using session from Vault."""
        try:
            session_id = credentials.get('session_id')
            if not session_id:
                self.logger.error("No session_id provided")
                return False
            
            # Get API keys from Vault
            api_keys = self.vault_client.get_platform_api_keys(Platform.TELEGRAM)
            if not api_keys:
                self.logger.error("Failed to get API keys from Vault")
                return False
            
            self.api_id = api_keys.get('api_id')
            self.api_hash = api_keys.get('api_hash')
            
            if not self.api_id or not self.api_hash:
                self.logger.error("Missing api_id or api_hash")
                return False
            
            # Get session file from Vault
            session_data = self.vault_client.get_session(Platform.TELEGRAM, session_id)
            if not session_data:
                self.logger.error(f"Failed to get session {session_id} from Vault")
                return False
            
            # Create temporary session file
            with tempfile.NamedTemporaryFile(suffix='.session', delete=False) as f:
                f.write(session_data)
                self.session_file_path = f.name
            
            # Initialize Telegram client
            self.client = TelegramClient(
                session=self.session_file_path,
                api_id=self.api_id,
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
            self.logger.info(f"✅ Telegram authenticated for user {me.first_name} ({me.id})")
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
            
            if isinstance(entity, Channel):
                await self._parse_channel(task, entity, message_limit)
            elif isinstance(entity, Chat):
                await self._parse_group(task, entity, message_limit)
            else:
                raise ValueError(f"Unsupported entity type: {type(entity)}")
            
            self.logger.info(f"✅ Completed parsing {normalized_target}")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to parse {target}: {e}")
            raise
    
    async def _parse_channel(self, task: ParseTask, channel: Channel, message_limit: int):
        """Parse messages from a Telegram channel."""
        self.logger.info(f"📱 Parsing channel: {channel.title}")
        
        message_count = 0
        parsed_results = []
        
        async for message in self.client.iter_messages(channel, limit=message_limit):
            if not isinstance(message, Message):
                continue
                
            # Parse message data
            result_data = await self._extract_message_data(task, message, channel)
            
            # Get author phone if available
            if message.from_id and isinstance(message.from_id, PeerUser):
                try:
                    user = await self.client.get_entity(message.from_id)
                    result_data['author_phone'] = await self._get_user_phone(user)
                    result_data['author_username'] = user.username
                    result_data['author_name'] = f"{user.first_name or ''} {user.last_name or ''}".strip()
                except Exception as e:
                    self.logger.debug(f"Could not get user data for message {message.id}: {e}")
            
            parsed_results.append(result_data)
            message_count += 1
            
            if message_count % 100 == 0:
                self.logger.info(f"📊 Processed {message_count} messages from channel...")
        
        self.logger.info(f"✅ Parsed {message_count} messages from channel {channel.title}")
        return parsed_results
    
    async def _parse_group(self, task: ParseTask, chat: Chat, message_limit: int):
        """Parse messages and participants from a Telegram group."""
        self.logger.info(f"👥 Parsing group: {chat.title}")
        
        parsed_results = []
        
        # Parse recent messages
        message_count = 0
        async for message in self.client.iter_messages(chat, limit=message_limit):
            if not isinstance(message, Message):
                continue
                
            result_data = await self._extract_message_data(task, message, chat)
            
            # Get author phone if available 
            if message.from_id and isinstance(message.from_id, PeerUser):
                try:
                    user = await self.client.get_entity(message.from_id)
                    result_data['author_phone'] = await self._get_user_phone(user)
                    result_data['author_username'] = user.username
                    result_data['author_name'] = f"{user.first_name or ''} {user.last_name or ''}".strip()
                except Exception as e:
                    self.logger.debug(f"Could not get user data for message {message.id}: {e}")
            
            parsed_results.append(result_data)
            message_count += 1
        
        # Parse group participants with phone numbers
        participant_count = 0
        try:
            async for participant in self.client.iter_participants(chat):
                if isinstance(participant, User):
                    participant_data = await self._extract_participant_data(task, participant, chat)
                    participant_data['author_phone'] = await self._get_user_phone(participant)
                    
                    parsed_results.append(participant_data)
                    participant_count += 1
                    
                    if participant_count % 50 == 0:
                        self.logger.info(f"📊 Processed {participant_count} participants...")
        
        except ChatAdminRequiredError:
            self.logger.warning("Cannot access participant list - admin rights required")
        except Exception as e:
            self.logger.warning(f"Error parsing participants: {e}")
        
        self.logger.info(f"✅ Parsed {message_count} messages and {participant_count} participants from group {chat.title}")
        return parsed_results
    
    async def _get_user_phone(self, user: User) -> Optional[str]:
        """Get user's phone number if accessible."""
        try:
            # Check if phone is already available in user object
            if hasattr(user, 'phone') and user.phone:
                phone = user.phone
                if not phone.startswith('+'):
                    phone = f"+{phone}"
                return phone
            
            # Try to get full user info
            try:
                full_user = await self.client(GetFullUserRequest(user))
                if hasattr(full_user.user, 'phone') and full_user.user.phone:
                    phone = full_user.user.phone
                    if not phone.startswith('+'):
                        phone = f"+{phone}"
                    return phone
            except Exception:
                pass
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Could not get phone for user {user.id}: {e}")
            return None
    
    async def _extract_message_data(self, task: ParseTask, message: Message, entity) -> Dict[str, Any]:
        """Extract data from a Telegram message."""
        return {
            'task_id': task.id,
            'platform': Platform.TELEGRAM,
            'source_id': str(entity.id),
            'source_name': getattr(entity, 'title', getattr(entity, 'username', 'Unknown')),
            'source_type': 'channel' if isinstance(entity, Channel) else 'group',
            'content_id': str(message.id),
            'content_type': 'message',
            'content_text': message.text or '',
            'author_id': str(message.from_id.user_id) if message.from_id else None,
            'author_username': None,  # Will be filled later
            'author_name': None,      # Will be filled later  
            'author_phone': None,     # Will be filled later
            'content_created_at': message.date,
            'views_count': getattr(message, 'views', 0) or 0,
            'has_media': message.media is not None,
            'media_count': 1 if message.media else 0,
            'media_types': self._get_media_types(message),
            'is_forwarded': message.forward is not None,
            'is_reply': message.reply_to is not None,
            'platform_data': {
                'message_id': message.id,
                'chat_id': entity.id,
                'forward_from': message.forward.from_name if message.forward else None,
                'reply_to_message_id': message.reply_to.reply_to_msg_id if message.reply_to else None,
            },
            'raw_data': message.to_dict()
        }
    
    async def _extract_participant_data(self, task: ParseTask, user: User, entity) -> Dict[str, Any]:
        """Extract data from a Telegram group participant."""
        return {
            'task_id': task.id,
            'platform': Platform.TELEGRAM,
            'source_id': str(entity.id),
            'source_name': getattr(entity, 'title', 'Unknown'),
            'source_type': 'group',
            'content_id': f"user_{user.id}",
            'content_type': 'participant',
            'content_text': f"Participant: {user.first_name or ''} {user.last_name or ''}",
            'author_id': str(user.id),
            'author_username': user.username,
            'author_name': f"{user.first_name or ''} {user.last_name or ''}".strip(),
            'author_phone': None,  # Will be filled later
            'content_created_at': datetime.now(),
            'platform_data': {
                'user_id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_bot': user.bot,
                'is_verified': user.verified,
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
        """Clean up Telegram client and session file."""
        try:
            if self.client:
                await self.client.disconnect()
                self.client = None
            
            if self.session_file_path and os.path.exists(self.session_file_path):
                os.unlink(self.session_file_path)
                self.session_file_path = None
                
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