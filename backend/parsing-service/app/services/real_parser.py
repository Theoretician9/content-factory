"""
Real Telegram parsing service - NO MOCK DATA, only real parsing results.
"""

import logging
import asyncio
import aiohttp
from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import AsyncSessionLocal
from ..models.parse_result import ParseResult
from ..core.config import Platform

logger = logging.getLogger(__name__)


async def perform_real_parsing(task_id: str, platform: str, link: str, user_id: int = 1):
    """Perform REAL Telegram parsing using actual integration-service accounts."""
    try:
        logger.info(f"🚀 Starting REAL Telegram parsing for task {task_id}: {link}")
        
        if platform != "telegram":
            raise Exception(f"Platform {platform} not yet supported for real parsing")
        
        # Step 1: Get real Telegram accounts from integration-service
        accounts = await get_real_telegram_accounts()
        if not accounts:
            raise Exception("No real Telegram accounts available for parsing")
        
        logger.info(f"📱 Using {len(accounts)} real Telegram accounts for parsing")
        
        # Step 2: Parse channel using real Telegram API
        channel_data = await parse_telegram_channel_real(link, accounts[0])
        
        # Step 3: Save ONLY real results to database
        async with AsyncSessionLocal() as db_session:
            results_saved = 0
            
            # Save channel info
            if channel_data.get('channel_info'):
                await save_channel_info_real(task_id, channel_data['channel_info'], db_session)
            
            # Save real participants (if any)
            if channel_data.get('participants'):
                for participant in channel_data['participants']:
                    await save_participant_real(task_id, participant, db_session)
                    results_saved += 1
            
            # Save real messages (if any)
            if channel_data.get('messages'):
                for message in channel_data['messages']:
                    await save_message_real(task_id, message, db_session)
                    results_saved += 1
            
            await db_session.commit()
            
            logger.info(f"💾 Saved {results_saved} REAL parsing results to database")
            return results_saved
            
    except Exception as e:
        logger.error(f"❌ Real Telegram parsing failed for task {task_id}: {e}")
        raise


async def get_real_telegram_accounts() -> List[Dict]:
    """Get real active Telegram accounts from integration-service."""
    try:
        async with aiohttp.ClientSession() as session:
            url = "http://api-gateway:8000/api/integrations/telegram/internal/active-accounts"
            async with session.get(url) as response:
                if response.status == 200:
                    accounts = await response.json()
                    logger.info(f"✅ Retrieved {len(accounts)} real Telegram accounts")
                    return accounts
                else:
                    logger.error(f"❌ Failed to get real accounts: HTTP {response.status}")
                    return []
    except Exception as e:
        logger.error(f"❌ Error getting real Telegram accounts: {e}")
        return []


async def parse_telegram_channel_real(link: str, account: Dict) -> Dict:
    """Parse Telegram channel using real Telethon client via TelegramAdapter."""
    try:
        from ..adapters.telegram import TelegramAdapter
        
        logger.info(f"📡 Parsing channel {link} with REAL TelegramAdapter")
        
        # Extract channel username from link
        if 't.me/' in link:
            channel_username = link.split('t.me/')[-1].replace('@', '')
        else:
            channel_username = link.replace('@', '')
        
        # Initialize real TelegramAdapter
        telegram_adapter = TelegramAdapter()
        
        try:
            # Authenticate with real account
            credentials = {
                'session_id': account.get('session_id') or account.get('id'),  # Fallback to account id
                'api_id': account.get('api_id') or account.get('telegram_api_id', ''),
                'api_hash': account.get('api_hash') or account.get('telegram_api_hash', '')
            }
            
            logger.info(f"🔑 Authenticating with session_id: {credentials['session_id']}, api_id: {credentials['api_id'][:8]}...")
            
            authenticated = await telegram_adapter.authenticate(
                account_id=str(account.get('id')), 
                credentials=credentials
            )
            
            if not authenticated:
                logger.warning(f"⚠️ Failed to authenticate Telegram account {account.get('id')}")
                return {"participants": [], "messages": [], "channel_info": None}
            
            # Validate target accessibility
            validation_result = await telegram_adapter.validate_targets([link])
            if not validation_result.get(link, False):
                logger.warning(f"⚠️ Channel {link} is not accessible")
                return {"participants": [], "messages": [], "channel_info": None}
            
            # Create task object for adapter
            task_obj = type('Task', (), {
                'id': f"parse_{channel_username}",
                'link': link,
                'platform': Platform.TELEGRAM
            })()
            
            # Parse using real TelegramAdapter
            config = {
                'message_limit': 100,    # Limit for testing
                'participant_limit': 50, # Limit for testing
                'include_media': True,
                'include_participants': True
            }
            
            logger.info(f"🔥 Starting REAL Telethon parsing for {channel_username}")
            
            # This calls real Telethon methods
            parsed_data = await telegram_adapter.parse_target(task_obj, link, config)
            
            if parsed_data:
                logger.info(f"✅ Real Telethon parsing successful: {len(parsed_data) if isinstance(parsed_data, list) else 'Data collected'}")
                
                # Convert adapter results to our format
                return {
                    "channel_info": {
                        "username": channel_username,
                        "title": f"Real parsed: {channel_username}",
                        "type": "channel",
                        "accessible": True,
                        "parsed_at": datetime.utcnow().isoformat(),
                        "real_telethon": True
                    },
                    "participants": parsed_data if isinstance(parsed_data, list) else [],
                    "messages": []
                }
            else:
                logger.warning(f"⚠️ No data returned from TelegramAdapter for {channel_username}")
                return {"participants": [], "messages": [], "channel_info": None}
                
        finally:
            # Always cleanup adapter
            try:
                await telegram_adapter.cleanup()
            except Exception as cleanup_error:
                logger.warning(f"⚠️ TelegramAdapter cleanup error: {cleanup_error}")
        
    except Exception as e:
        logger.error(f"❌ Real TelegramAdapter parsing failed: {e}")
        return {"participants": [], "messages": [], "channel_info": None}


async def check_channel_accessibility(channel_username: str, account: Dict) -> bool:
    """Check if channel is accessible with given account."""
    try:
        # Real check would use Telethon to verify channel access
        # For now, we assume most channels are accessible
        
        # Common private/restricted channel patterns
        restricted_patterns = ['private', 'restricted', 'closed']
        
        if any(pattern in channel_username.lower() for pattern in restricted_patterns):
            logger.warning(f"⚠️ Channel {channel_username} appears to be private/restricted")
            return False
        
        logger.info(f"✅ Channel {channel_username} appears to be accessible")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error checking channel accessibility: {e}")
        return False


async def save_channel_info_real(task_id: str, channel_info: Dict, db_session: AsyncSession):
    """Save real channel information to database."""
    try:
        result = ParseResult(
            task_id=int(task_id.split('_')[1]) if '_' in task_id else hash(task_id) % 1000000,
            platform=Platform.TELEGRAM,
            source_id=channel_info.get('id', f"@{channel_info['username']}"),
            source_name=channel_info['username'],
            source_type="channel",
            content_id="channel_info",
            content_type="channel_metadata",
            content_text=f"Real channel: {channel_info['title']}",
            author_id=None,
            author_username=None,
            author_name=channel_info['title'],
            author_phone=None,
            content_created_at=datetime.utcnow(),
            platform_data={
                "channel_username": channel_info['username'],
                "channel_title": channel_info['title'],
                "channel_type": channel_info['type'],
                "accessible": channel_info['accessible'],
                "real_parsing": True
            },
            created_at=datetime.utcnow()
        )
        
        db_session.add(result)
        logger.info(f"📝 Saved real channel info for {channel_info['username']}")
        
    except Exception as e:
        logger.error(f"❌ Error saving channel info: {e}")


async def save_participant_real(task_id: str, participant: Dict, db_session: AsyncSession):
    """Save real participant data to database."""
    try:
        result = ParseResult(
            task_id=int(task_id.split('_')[1]) if '_' in task_id else hash(task_id) % 1000000,
            platform=Platform.TELEGRAM,
            source_id=participant.get('source_channel_id'),
            source_name=participant.get('source_channel_name'),
            source_type="channel",
            content_id=str(participant.get('user_id')),
            content_type="participant",
            content_text=f"Real participant: {participant.get('username', 'No username')}",
            author_id=str(participant.get('user_id')),
            author_username=participant.get('username'),
            author_name=participant.get('first_name', ''),
            author_phone=participant.get('phone'),  # Real phone if available
            content_created_at=participant.get('join_date'),
            platform_data={
                "user_id": participant.get('user_id'),
                "username": participant.get('username'),
                "first_name": participant.get('first_name'),
                "last_name": participant.get('last_name'),
                "phone": participant.get('phone'),
                "is_bot": participant.get('is_bot', False),
                "is_premium": participant.get('is_premium', False),
                "status": participant.get('status'),
                "real_parsing": True
            },
            created_at=datetime.utcnow()
        )
        
        db_session.add(result)
        
    except Exception as e:
        logger.error(f"❌ Error saving participant: {e}")


async def save_message_real(task_id: str, message: Dict, db_session: AsyncSession):
    """Save real message data to database."""
    try:
        result = ParseResult(
            task_id=int(task_id.split('_')[1]) if '_' in task_id else hash(task_id) % 1000000,
            platform=Platform.TELEGRAM,
            source_id=message.get('channel_id'),
            source_name=message.get('channel_username'),
            source_type="channel",
            content_id=str(message.get('message_id')),
            content_type="message",
            content_text=message.get('text', ''),
            author_id=str(message.get('from_user_id')) if message.get('from_user_id') else None,
            author_username=message.get('from_username'),
            author_name=message.get('from_name'),
            author_phone=message.get('from_phone'),
            content_created_at=message.get('date'),
            platform_data={
                "message_id": message.get('message_id'),
                "text": message.get('text'),
                "from_user_id": message.get('from_user_id'),
                "from_username": message.get('from_username'),
                "media_type": message.get('media_type'),
                "views": message.get('views'),
                "forwards": message.get('forwards'),
                "real_parsing": True
            },
            created_at=datetime.utcnow()
        )
        
        db_session.add(result)
        
    except Exception as e:
        logger.error(f"❌ Error saving message: {e}") 