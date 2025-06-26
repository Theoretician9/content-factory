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
from ..models.parse_task import ParseTask
from ..core.config import Platform
from ..core.vault import get_vault_client
from ..adapters.telegram import TelegramAdapter
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def get_task_db_id(task_id: str, db_session: AsyncSession) -> Optional[int]:
    """Get the database ID for a task by its string task_id."""
    try:
        # Query to find the task by task_id string
        stmt = select(ParseTask.id).where(ParseTask.task_id == task_id)
        result = await db_session.execute(stmt)
        db_id = result.scalar_one_or_none()
        
        if db_id:
            logger.info(f"✅ Found task DB ID: {db_id} for task_id: {task_id}")
            return db_id
        else:
            logger.warning(f"⚠️ Task not found in database: {task_id}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error finding task ID: {e}")
        return None


async def save_parsing_results(task_id: str, results: List[Dict]):
    """Save parsing results to database."""
    try:
        async with AsyncSessionLocal() as db_session:
            # Get task database ID
            task_db_id = await get_task_db_id(task_id, db_session)
            if not task_db_id:
                logger.error(f"❌ Task {task_id} not found in database, cannot save results")
                return 0
            
            results_saved = 0
            
            for result_data in results:
                try:
                    # Create ParseResult from TelegramAdapter data
                    result = ParseResult(
                        task_id=task_db_id,
                        platform=result_data.get('platform', Platform.TELEGRAM),
                        source_id=result_data.get('source_id', 'unknown'),
                        source_name=result_data.get('source_name', 'unknown'),
                        source_type=result_data.get('source_type', 'channel'),
                        content_id=result_data.get('content_id', 'unknown'),
                        content_type=result_data.get('content_type', 'user'),
                        content_text=result_data.get('content_text', ''),
                        author_id=result_data.get('author_id'),
                        author_username=result_data.get('author_username'),
                        author_name=result_data.get('author_name', ''),
                        author_phone=result_data.get('author_phone'),
                        content_created_at=result_data.get('content_created_at') or datetime.utcnow(),
                        views_count=result_data.get('views_count', 0),
                        has_media=result_data.get('has_media', False),
                        media_count=result_data.get('media_count', 0),
                        media_types=result_data.get('media_types', []),
                        is_forwarded=result_data.get('is_forwarded', False),
                        is_reply=result_data.get('is_reply', False),
                        platform_data=result_data.get('platform_data', {}),
                        raw_data=result_data.get('raw_data', {}),
                        created_at=datetime.utcnow()
                    )
                    
                    db_session.add(result)
                    results_saved += 1
                    
                except Exception as e:
                    logger.error(f"❌ Error saving individual result: {e}")
                    continue
            
            await db_session.commit()
            logger.info(f"💾 Saved {results_saved} parsing results to database")
            return results_saved
            
    except Exception as e:
        logger.error(f"❌ Error saving parsing results: {e}")
        return 0


async def perform_real_parsing(task_id: str, platform: str, link: str, user_id: int = 1):
    """Perform REAL Telegram parsing using actual integration-service accounts."""
    return await perform_real_parsing_with_progress(task_id, platform, link, user_id, None)


async def perform_real_parsing_with_progress(
    task_id: str,
    platform: str, 
    link: str,
    user_id: int = 1,
    progress_callback=None,
    message_limit: int = 100,
    speed_config=None  # New parameter for parsing speed configuration
) -> int:
    """
    ГЛАВНАЯ функция парсинга - оркестрирует весь процесс:
    
    1. Получение активных аккаунтов от Integration Service
    2. Создание и настройка Platform Adapter
    3. Аутентификация с платформой
    4. Парсинг с real-time progress callbacks и speed configuration
    5. Сохранение результатов в PostgreSQL
    6. Cleanup всех ресурсов
    """
    
    if speed_config:
        logger.info(f"🚀 Starting REAL parsing for task {task_id}: {link} (USER LIMIT: {message_limit}, SPEED: {speed_config.name})")
    else:
        logger.info(f"🚀 Starting REAL parsing for task {task_id}: {link} (USER LIMIT: {message_limit})")
    
    try:
        # Step 1: Get real Telegram accounts from integration-service
        accounts = await get_real_telegram_accounts()
        if not accounts:
            raise Exception("No real Telegram accounts available for parsing")
        
        logger.info(f"📱 Using {len(accounts)} real Telegram accounts for parsing")
        
        # Step 2: Select best account (least recently used)
        selected_account = min(accounts, key=lambda x: x.get('last_used_at', ''))
        session_id = selected_account.get('session_id')
        
        # Step 3: Get API credentials from Vault + session data from Integration Service
        vault_client = get_vault_client()
        api_keys = vault_client.get_secret("integration-service")
        
        credentials = {
            'session_id': session_id,
            'api_id': api_keys.get('telegram_api_id'),
            'api_hash': api_keys.get('telegram_api_hash'),
            'session_data': selected_account.get('session_data')  # From Integration DB
        }
        
        # Step 4: Create and authenticate adapter
        adapter = TelegramAdapter()
        
        if not await adapter.authenticate(session_id, credentials):
            raise Exception(f"Failed to authenticate with session {session_id}")
        
        # Step 5: Parse target with progress tracking and speed configuration
        if speed_config:
            logger.info(f"🔧 TelegramAdapter config: message_limit={message_limit}, speed={speed_config.name}")
        else:
            logger.info(f"🔧 TelegramAdapter config: message_limit={message_limit}")
        
        # Create mock task object for adapter compatibility
        from app.models.parse_task import ParseTask
        from datetime import datetime
        
        # Get task from database or create minimal task object
        async with AsyncSessionLocal() as db_session:
            task_db_id = await get_task_db_id(task_id, db_session)
            
            if task_db_id:
                # Use existing task
                from sqlalchemy import select
                stmt = select(ParseTask).where(ParseTask.id == task_db_id)
                result = await db_session.execute(stmt)
                task = result.scalar_one_or_none()
            else:
                # Create minimal task object for compatibility
                task = type('Task', (), {'id': 1, 'task_id': task_id})()
        
        # Create config dictionary for adapter
        config = {
            'message_limit': message_limit,
            'progress_callback': progress_callback,
            'speed_config': speed_config
        }
        
        results = await adapter.parse_target(task, link, config)
        
        # Step 6: Save results to PostgreSQL database
        if results:
            await save_parsing_results(task_id, results)
        
        # Step 7: Cleanup resources
        await adapter.cleanup()
        
        result_count = len(results) if results else 0
        if speed_config:
            logger.info(f"✅ REAL parsing completed with {speed_config.name} speed: {result_count} results")
        else:
            logger.info(f"✅ REAL parsing completed: {result_count} results")
        
        return result_count
        
    except Exception as e:
        logger.error(f"❌ Real parsing failed: {e}")
        raise


async def get_real_telegram_accounts() -> List[Dict]:
    """Get real active Telegram accounts from integration-service."""
    try:
        async with aiohttp.ClientSession() as session:
            url = "http://integration-service:8000/api/v1/telegram/internal/active-accounts"
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
    return await parse_telegram_channel_real_with_progress(link, account, None)


async def parse_telegram_channel_real_with_progress(link: str, account: Dict, progress_callback=None, message_limit: int = 100) -> Dict:
    """Parse Telegram channel with real-time progress updates."""
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
            # Authenticate with real account using data from integration-service
            credentials = {
                'session_id': account.get('session_id') or account.get('id'),
                'api_id': account.get('api_id'),
                'api_hash': account.get('api_hash'),
                'session_data': account.get('session_data')  # Session файл от integration-service
            }
            
            logger.info(f"🔑 REAL_PARSER: Using integration-service credentials: session_id={credentials['session_id']}, api_id={credentials['api_id']}, has_session_data={credentials['session_data'] is not None}")
            
            if not credentials['session_data']:
                logger.warning(f"⚠️ REAL_PARSER: No session data provided by integration-service for account {account.get('id')}")
                return {"participants": [], "messages": [], "channel_info": None}
            
            # Authenticate with TelegramAdapter using integration-service data
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
            
            # Parse using real TelegramAdapter with progress callback
            config = {
                'message_limit': message_limit,    # Use provided message_limit
                'participant_limit': message_limit, # Same limit for participants
                'include_media': True,
                'include_participants': True,
                'progress_callback': progress_callback  # Pass callback to adapter
            }
            
            logger.info(f"🔧 TelegramAdapter config: message_limit={message_limit}, progress_callback={progress_callback is not None}")
            
            logger.info(f"🔥 Starting REAL Telethon parsing for {channel_username}")
            
            # This calls real Telethon methods with progress tracking
            parsed_data = await telegram_adapter.parse_target(task_obj, link, config)
            
            if parsed_data:
                logger.info(f"✅ Real Telethon parsing successful: {len(parsed_data) if isinstance(parsed_data, list) else 'Data collected'}")
                
                # Separate messages and participants from TelegramAdapter data
                messages = []
                participants = []
                
                if isinstance(parsed_data, list):
                    logger.info(f"🔍 DEBUG: Processing {len(parsed_data)} items from TelegramAdapter")
                    for item in parsed_data:
                        content_type = item.get('content_type')
                        if content_type == 'message':
                            messages.append(item)
                        elif content_type in ['participant', 'user']:  # Support both old and new format
                            participants.append(item)
                        elif content_type in ['channel_metadata', 'group_metadata']:
                            # Channel/Group info - also count as participants for now
                            participants.append(item)
                        else:
                            logger.warning(f"⚠️ Unknown content_type: {content_type}")
                    
                    logger.info(f"📊 Parsed data breakdown: {len(messages)} messages, {len(participants)} users/participants")
                
                return {
                    "channel_info": {
                        "username": channel_username,
                        "title": f"Real parsed: {channel_username}",
                        "type": "channel",
                        "accessible": True,
                        "parsed_at": datetime.utcnow().isoformat(),
                        "real_telethon": True
                    },
                    "participants": participants,
                    "messages": messages
                }
            else:
                logger.warning(f"⚠️ No data returned from TelegramAdapter for {channel_username}")
                return {"participants": [], "messages": [], "channel_info": None}
                
        finally:
            # Always cleanup adapter with timeout protection
            try:
                # Защита от зависания cleanup
                await asyncio.wait_for(telegram_adapter.cleanup(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("⚠️ TelegramAdapter cleanup timeout, forcing exit")
            except (asyncio.CancelledError, GeneratorExit):
                logger.warning("⚠️ TelegramAdapter cleanup cancelled")
            except Exception as cleanup_error:
                logger.warning(f"⚠️ TelegramAdapter cleanup error: {cleanup_error}")
            finally:
                # Принудительно очищаем ссылку
                telegram_adapter = None
        
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


async def save_channel_info_real(task_db_id: int, channel_info: Dict, db_session: AsyncSession):
    """Save real channel information to database."""
    try:
        username = channel_info.get('username', 'unknown')
        result = ParseResult(
            task_id=task_db_id,
            platform=Platform.TELEGRAM,
            source_id=channel_info.get('id') or f"@{username}",
            source_name=username,
            source_type="channel",
            content_id="channel_info",
            content_type="channel_metadata",
            content_text=f"Real channel: {channel_info.get('title', username)}",
            author_id=None,
            author_username=None,
            author_name=channel_info.get('title', username),
            author_phone=None,
            content_created_at=datetime.utcnow(),
            platform_data={
                "channel_username": username,
                "channel_title": channel_info.get('title', username),
                "channel_type": channel_info.get('type', 'channel'),
                "accessible": channel_info.get('accessible', True),
                "real_parsing": True
            },
            created_at=datetime.utcnow()
        )
        
        db_session.add(result)
        logger.info(f"📝 Saved real channel info for {username}")
        
    except Exception as e:
        logger.error(f"❌ Error saving channel info: {e}")


async def save_participant_real(task_db_id: int, participant: Dict, db_session: AsyncSession):
    """Save real participant data to database."""
    try:
        # Use TelegramAdapter data format
        result = ParseResult(
            task_id=task_db_id,
            platform=Platform.TELEGRAM,
            source_id=participant.get('source_id') or 'unknown',  # From TelegramAdapter
            source_name=participant.get('source_name') or 'unknown',  # From TelegramAdapter
            source_type=participant.get('source_type', 'channel'),
            content_id=participant.get('content_id') or 'unknown',  # From TelegramAdapter
            content_type=participant.get('content_type', 'participant'),
            content_text=participant.get('content_text', 'Real participant'),
            author_id=participant.get('author_id'),
            author_username=participant.get('author_username'),
            author_name=participant.get('author_name', ''),
            author_phone=participant.get('author_phone'),  # Real phone if available
            content_created_at=participant.get('content_created_at') or datetime.utcnow(),
            platform_data=participant.get('platform_data', {}),
            created_at=datetime.utcnow()
        )
        
        db_session.add(result)
        
    except Exception as e:
        logger.error(f"❌ Error saving participant: {e}")


async def save_message_real(task_db_id: int, message: Dict, db_session: AsyncSession):
    """Save real message data to database."""
    try:
        # Use TelegramAdapter data format
        result = ParseResult(
            task_id=task_db_id,
            platform=Platform.TELEGRAM,
            source_id=message.get('source_id') or 'unknown',  # From TelegramAdapter
            source_name=message.get('source_name') or 'unknown',  # From TelegramAdapter
            source_type=message.get('source_type', 'channel'),
            content_id=message.get('content_id') or 'unknown',  # From TelegramAdapter
            content_type=message.get('content_type', 'message'),
            content_text=message.get('content_text', ''),
            author_id=message.get('author_id'),
            author_username=message.get('author_username'),
            author_name=message.get('author_name', ''),
            author_phone=message.get('author_phone'),
            content_created_at=message.get('content_created_at') or datetime.utcnow(),
            views_count=message.get('views_count', 0),
            has_media=message.get('has_media', False),
            media_count=message.get('media_count', 0),
            is_forwarded=message.get('is_forwarded', False),
            is_reply=message.get('is_reply', False),
            platform_data=message.get('platform_data', {}),
            created_at=datetime.utcnow()
        )
        
        db_session.add(result)
        
    except Exception as e:
        logger.error(f"❌ Error saving message: {e}") 