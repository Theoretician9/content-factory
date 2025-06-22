"""
Telegram platform adapter for parsing channels and groups.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime, timedelta
import json

from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError, AuthKeyUnregisteredError, UserDeactivatedError,
    ChatAdminRequiredError, ChannelPrivateError
)
from telethon.tl.types import Channel, Chat, User, Message

from .base import BasePlatformAdapter
from ..core.config import Platform, settings
from ..core.vault import get_vault_client
from ..models.parse_task import ParseTask
from ..models.parse_result import ParseResult

logger = logging.getLogger(__name__)


class TelegramAdapter(BasePlatformAdapter):
    """Telegram platform adapter for parsing channels and groups."""
    
    def __init__(self):
        super().__init__(Platform.TELEGRAM)
        self.client: Optional[TelegramClient] = None
        self.session_file_path: Optional[str] = None
        self.vault_client = get_vault_client()
        
    @property
    def platform_name(self) -> str:
        return "Telegram"
    
    async def authenticate(self, account_id: str, credentials: Dict[str, Any]) -> bool:
        """
        Authenticate with Telegram using session from Vault.
        
        Args:
            account_id: Account identifier in integration service
            credentials: Should contain session_id for Vault lookup
            
        Returns:
            True if authentication successful
        """
        try:
            session_id = credentials.get('session_id')
            if not session_id:
                self.logger.error("No session_id provided in credentials")
                return False
            
            # Get Telegram API credentials from Vault
            api_keys = self.vault_client.get_platform_api_keys(Platform.TELEGRAM)
            if not api_keys:
                self.logger.error("Failed to get Telegram API keys from Vault")
                return False
            
            api_id = api_keys.get('api_id')
            api_hash = api_keys.get('api_hash')
            
            if not api_id or not api_hash:
                self.logger.error("Missing API ID or API Hash in Vault")
                return False
            
            # Create temporary session file from Vault
            self.session_file_path = self.vault_client.create_temp_session_file(session_id)
            if not self.session_file_path:
                self.logger.error(f"Failed to create session file for {session_id}")
                return False
            
            # Initialize Telegram client
            self.client = TelegramClient(
                self.session_file_path,
                int(api_id),
                api_hash,
                system_version="4.16.30-vxCUSTOM"
            )
            
            # Connect and check authentication
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                self.logger.error("Telegram session is not authorized")
                await self.cleanup()
                return False
            
            # Get current user info
            me = await self.client.get_me()
            self.logger.info(f"✅ Authenticated as @{me.username} ({me.first_name})")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Telegram authentication failed: {e}")
            await self.cleanup()
            return False
    
    async def validate_targets(self, targets: List[str]) -> Dict[str, bool]:
        """
        Validate if Telegram targets (channels/groups) exist and are accessible.
        
        Args:
            targets: List of channel/group usernames or IDs
            
        Returns:
            Dictionary mapping target -> validity status
        """
        if not self.client:
            return {target: False for target in targets}
        
        results = {}
        
        for target in targets:
            try:
                normalized_target = self.normalize_target(target)
                entity = await self.client.get_entity(normalized_target)
                results[target] = True
                
                # Log entity info
                if isinstance(entity, Channel):
                    self.logger.info(f"✅ Found channel: {entity.title} (@{entity.username})")
                elif isinstance(entity, Chat):
                    self.logger.info(f"✅ Found group: {entity.title}")
                    
            except Exception as e:
                self.logger.warning(f"❌ Cannot access target '{target}': {e}")
                results[target] = False
        
        return results
    
    async def parse_target(self, task: ParseTask, target: str, config: Dict[str, Any]):
        """
        Parse messages from a Telegram target (channel or group).
        
        Args:
            task: Parse task instance
            target: Target channel/group identifier
            config: Parsing configuration
        """
        if not self.client:
            raise Exception("Client not authenticated")
        
        try:
            normalized_target = self.normalize_target(target)
            entity = await self.client.get_entity(normalized_target)
            
            # Extract configuration
            message_limit = config.get('message_limit', 10000)
            include_media = config.get('include_media', True)
            date_from = self._parse_date(config.get('date_from'))
            date_to = self._parse_date(config.get('date_to'))
            filters = config.get('filters', {})
            
            self.logger.info(f"📥 Starting to parse {target} (limit: {message_limit})")
            
            # Get entity info for results
            entity_info = await self._get_entity_info(entity)
            
            # Parse messages
            message_count = 0
            async for message in self.client.iter_messages(
                entity,
                limit=message_limit,
                offset_date=date_to,
                reverse=False
            ):
                try:
                    # Check date filter
                    if date_from and message.date < date_from:
                        continue
                    
                    # Apply text filters
                    if not self._apply_filters(message, filters):
                        continue
                    
                    # Create ParseResult
                    result = self._create_parse_result(
                        task=task,
                        message=message,
                        entity_info=entity_info,
                        include_media=include_media
                    )
                    
                    if result:
                        yield result
                        message_count += 1
                        
                        # Update progress
                        if message_count % 100 == 0:
                            progress = min(100, int((message_count / message_limit) * 100))
                            self.logger.info(f"📊 Progress: {message_count}/{message_limit} ({progress}%)")
                    
                except Exception as e:
                    self.logger.error(f"Error processing message {message.id}: {e}")
                    continue
            
            self.logger.info(f"✅ Completed parsing {target}: {message_count} messages")
            
        except FloodWaitError as e:
            self.logger.warning(f"⏰ Hit rate limit, need to wait {e.seconds} seconds")
            raise
        except (ChannelPrivateError, ChatAdminRequiredError) as e:
            self.logger.error(f"❌ Access denied to {target}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"❌ Failed to parse {target}: {e}")
            raise
    
    def _create_parse_result(
        self, 
        task: ParseTask, 
        message: Message,
        entity_info: Dict[str, Any],
        include_media: bool = True
    ) -> Optional[ParseResult]:
        """Create ParseResult from Telegram message."""
        
        try:
            # Extract URLs, mentions, hashtags
            urls = self._extract_urls(message.text) if message.text else []
            mentions = self._extract_mentions(message.text) if message.text else []
            hashtags = self._extract_hashtags(message.text) if message.text else []
            
            # Media information
            has_media = bool(message.media)
            media_count = 1 if has_media else 0
            media_types = []
            
            if has_media and message.media:
                media_types = [self._get_media_type(message.media)]
            
            # Author information
            author_info = self._get_author_info(message)
            
            # Create result
            result = ParseResult(
                task_id=task.id,
                platform=Platform.TELEGRAM,
                source_id=str(entity_info['id']),
                source_name=entity_info['title'],
                source_type=entity_info['type'],
                content_id=str(message.id),
                content_type='message',
                content_text=message.text or '',
                author_id=author_info.get('id'),
                author_username=author_info.get('username'),
                author_name=author_info.get('name'),
                content_created_at=message.date,
                views_count=message.views or 0,
                likes_count=0,  # Telegram doesn't have likes
                shares_count=message.forwards or 0,
                comments_count=0,  # Would need separate API call
                has_media=has_media,
                media_count=media_count,
                media_types=media_types,
                urls=urls,
                mentions=mentions,
                hashtags=hashtags,
                is_forwarded=bool(message.forward),
                is_reply=bool(message.reply_to),
                is_edited=bool(message.edit_date),
                platform_data={
                    'message_id': message.id,
                    'chat_id': entity_info['id'],
                    'forward_from': message.forward.from_id if message.forward else None,
                    'reply_to_message_id': message.reply_to.reply_to_msg_id if message.reply_to else None,
                    'edit_date': message.edit_date.isoformat() if message.edit_date else None,
                    'post_author': message.post_author,
                    'grouped_id': message.grouped_id
                },
                raw_data=message.to_dict()
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to create ParseResult from message {message.id}: {e}")
            return None
    
    async def _get_entity_info(self, entity) -> Dict[str, Any]:
        """Get information about Telegram entity."""
        info = {
            'id': entity.id,
            'title': getattr(entity, 'title', 'Unknown'),
            'username': getattr(entity, 'username', None),
            'type': 'channel' if isinstance(entity, Channel) else 'group'
        }
        
        if isinstance(entity, Channel):
            info.update({
                'broadcast': entity.broadcast,
                'megagroup': entity.megagroup,
                'verified': entity.verified,
                'participants_count': getattr(entity, 'participants_count', 0)
            })
        
        return info
    
    def _get_author_info(self, message: Message) -> Dict[str, Any]:
        """Extract author information from message."""
        author_info = {}
        
        if message.from_id:
            author_info['id'] = str(message.from_id)
        
        # For channel posts, use post_author if available
        if message.post_author:
            author_info['name'] = message.post_author
        
        return author_info
    
    def _apply_filters(self, message: Message, filters: Dict[str, Any]) -> bool:
        """Apply text filters to message."""
        if not message.text:
            return not filters.get('require_text', False)
        
        text_lower = message.text.lower()
        
        # Keyword filters
        keywords = filters.get('keywords', [])
        if keywords:
            if not any(keyword.lower() in text_lower for keyword in keywords):
                return False
        
        # Exclude keywords
        exclude_keywords = filters.get('exclude_keywords', [])
        if exclude_keywords:
            if any(keyword.lower() in text_lower for keyword in exclude_keywords):
                return False
        
        # Minimum length
        min_length = filters.get('min_length', 0)
        if len(message.text) < min_length:
            return False
        
        return True
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime."""
        if not date_str:
            return None
        
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            self.logger.warning(f"Invalid date format: {date_str}")
            return None
    
    def _extract_urls(self, text: str) -> List[str]:
        """Extract URLs from text."""
        import re
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        return re.findall(url_pattern, text)
    
    def _extract_mentions(self, text: str) -> List[str]:
        """Extract @mentions from text."""
        import re
        mention_pattern = r'@([a-zA-Z0-9_]+)'
        return re.findall(mention_pattern, text)
    
    def _extract_hashtags(self, text: str) -> List[str]:
        """Extract #hashtags from text."""
        import re
        hashtag_pattern = r'#([a-zA-Z0-9_]+)'
        return re.findall(hashtag_pattern, text)
    
    def _get_media_type(self, media) -> str:
        """Get media type from Telegram media object."""
        media_type = type(media).__name__.lower()
        if 'photo' in media_type:
            return 'photo'
        elif 'video' in media_type:
            return 'video'
        elif 'audio' in media_type:
            return 'audio'
        elif 'document' in media_type:
            return 'document'
        else:
            return 'unknown'
    
    async def cleanup(self):
        """Clean up Telegram client and session file."""
        try:
            if self.client:
                await self.client.disconnect()
                self.client = None
            
            if self.session_file_path:
                self.vault_client.cleanup_temp_file(self.session_file_path)
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
        
        # Remove @ prefix for username lookup
        if target.startswith('@'):
            return target  # Keep @ for Telegram
        
        return target 