"""Telegram parsing worker tasks."""

from celery import current_task
from celery.utils.log import get_task_logger
from .celery_app import app as celery_app
from ..core.config import settings
import asyncio
import time

logger = get_task_logger(__name__)


async def _release_account_after_parsing(
    target: str, 
    user_id: int, 
    success: bool, 
    messages_parsed: int = 0, 
    error_message: str = None
):
    """Освободить аккаунт через Account Manager после завершения парсинга"""
    try:
        from ..clients.account_manager_client import AccountManagerClient
        
        account_manager = AccountManagerClient()
        
        # Формируем статистику использования для парсинга
        usage_stats = {
            "invites_sent": 0,  # Парсинг не отправляет приглашения
            "messages_sent": 0,  # Парсинг не отправляет сообщения 
            "contacts_added": 0,  # Парсинг не добавляет контакты
            "channels_used": [target],  # Парсенный канал/группа
            "success": success,
            "error_type": "parsing_error" if not success else None,
            "error_message": error_message
        }
        
        # Освобождаем все аккаунты, заблокированные parsing-service
        # Это безопасный способ освободить аккаунты после завершения задач
        result = await account_manager.release_all_accounts()
        
        if result.get('success'):
            released_count = result.get('released_count', 0)
            logger.info(f"✅ Account Manager: Released {released_count} accounts after parsing {target}")
        else:
            logger.warning(f"⚠️ Account Manager: Failed to release accounts: {result}")
            
    except Exception as e:
        logger.error(f"❌ Error releasing accounts after parsing {target}: {e}")


@celery_app.task(bind=True, name="telegram_parse_channel")
def telegram_parse_channel(self, channel_username: str, user_id: int, **kwargs):
    """Parse Telegram channel messages."""
    logger.info(f"🚀 Starting Telegram channel parsing: {channel_username}")
    
    try:
        # Update task status
        current_task.update_state(
            state="PROGRESS",
            meta={"status": "Starting channel parsing", "progress": 0}
        )
        
        # TODO: Implement actual Telegram parsing logic
        # This would involve:
        # 1. Get user's Telegram session from Integration Service
        # 2. Connect to Telegram API
        # 3. Parse channel messages
        # 4. Store results in database
        
        # Simulate work for now
        for i in range(5):
            time.sleep(2)
            current_task.update_state(
                state="PROGRESS",
                meta={"status": f"Processing messages", "progress": (i + 1) * 20}
            )
        
        result = {
            "channel": channel_username,
            "user_id": user_id,
            "messages_parsed": 150,     # Mock data
            "status": "completed",
            "timestamp": time.time()
        }
        
        # Освобождаем аккаунт через Account Manager
        asyncio.run(_release_account_after_parsing(channel_username, user_id, True, 150))
        
        logger.info(f"✅ Completed Telegram channel parsing: {channel_username}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Error parsing Telegram channel {channel_username}: {e}")
        
        # Освобождаем аккаунт даже при ошибке
        asyncio.run(_release_account_after_parsing(channel_username, user_id, False, 0, str(e)))
        
        current_task.update_state(
            state="FAILURE",
            meta={"error": str(e), "channel": channel_username}
        )
        raise


@celery_app.task(bind=True, name="telegram_parse_group")
def telegram_parse_group(self, group_id: str, user_id: int, **kwargs):
    """Parse Telegram group messages."""
    logger.info(f"🚀 Starting Telegram group parsing: {group_id}")
    
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"status": "Starting group parsing", "progress": 0}
        )
        
        # TODO: Implement actual group parsing logic
        
        # Simulate work
        for i in range(3):
            time.sleep(3)
            current_task.update_state(
                state="PROGRESS",
                meta={"status": "Processing group messages", "progress": (i + 1) * 33}
            )
        
        result = {
            "group_id": group_id,
            "user_id": user_id,
            "messages_parsed": 87,     # Mock data
            "status": "completed",
            "timestamp": time.time()
        }
        
        # Освобождаем аккаунт через Account Manager
        asyncio.run(_release_account_after_parsing(group_id, user_id, True, 87))
        
        logger.info(f"✅ Completed Telegram group parsing: {group_id}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Error parsing Telegram group {group_id}: {e}")
        
        # Освобождаем аккаунт даже при ошибке
        asyncio.run(_release_account_after_parsing(group_id, user_id, False, 0, str(e)))
        
        current_task.update_state(
            state="FAILURE",
            meta={"error": str(e), "group_id": group_id}
        )
        raise


@celery_app.task(bind=True, name="telegram_search_communities")
def telegram_search_communities(self, keywords: str, user_id: int, offset: int = 0, limit: int = 10, **kwargs):
    """Search Telegram communities by keywords using real Telethon integration."""
    logger.info(f"🚀 Starting real Telegram community search: '{keywords}' (user: {user_id}, offset: {offset}, limit: {limit})")
    
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"status": "Initializing search", "progress": 0}
        )
        
        # Import async components
        import asyncio
        from ..adapters.telegram import TelegramAdapter
        from ..core.integration_client import get_integration_client
        from ..core.vault import get_vault_client
        
        async def perform_search():
            # Get active Telegram accounts
            integration_client = get_integration_client()
            accounts = await integration_client.get_active_telegram_accounts()
            
            if not accounts:
                raise Exception("No active Telegram accounts available for search")
            
            # Select first available account
            selected_account = accounts[0]
            session_id = selected_account.get('session_id')
            
            # Update progress
            current_task.update_state(
                state="PROGRESS", 
                meta={"status": f"Authenticating with account {session_id}", "progress": 20}
            )
            
            # Get credentials
            vault_client = get_vault_client()
            api_keys = vault_client.get_secret("integration-service")
            
            credentials = {
                'session_id': session_id,
                'api_id': api_keys.get('telegram_api_id'),
                'api_hash': api_keys.get('telegram_api_hash'),
                'session_data': selected_account.get('session_data')
            }
            
            # Create and authenticate adapter
            adapter = TelegramAdapter()
            
            if not await adapter.authenticate(session_id, credentials):
                raise Exception(f"Failed to authenticate with Telegram account {session_id}")
            
            # Update progress
            current_task.update_state(
                state="PROGRESS",
                meta={"status": "Searching communities", "progress": 50}
            )
            
            try:
                # Perform actual search
                search_results = await adapter.search_communities(
                    query=keywords,
                    offset=offset,
                    limit=limit
                )
                
                # Update progress
                current_task.update_state(
                    state="PROGRESS",
                    meta={"status": "Processing results", "progress": 80}
                )
                
                # Cleanup
                await adapter.cleanup()
                
                return search_results
                
            except Exception as search_error:
                await adapter.cleanup()
                raise search_error
        
        # Run async function
        if hasattr(asyncio, 'run'):
            # Python 3.7+
            search_results = asyncio.run(perform_search())
        else:
            # Python 3.6
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                search_results = loop.run_until_complete(perform_search())
            finally:
                loop.close()
        
        # Final result
        result = {
            "keywords": keywords,
            "user_id": user_id,
            "offset": offset,
            "limit": limit,
            "communities_found": search_results.get('results', []),
            "total_found": search_results.get('total_found', 0),
            "has_more": search_results.get('has_more', False),
            "status": "completed",
            "timestamp": time.time()
        }
        
        # Освобождаем аккаунт через Account Manager
        asyncio.run(_release_account_after_parsing(
            f"search:{keywords}", 
            user_id, 
            True, 
            result.get('total_found', 0)
        ))
        
        logger.info(f"✅ Completed real Telegram community search: {result['total_found']} total found, {len(result['communities_found'])} returned")
        return result
        
    except Exception as e:
        logger.error(f"❌ Error in real Telegram community search: {e}")
        
        # Освобождаем аккаунт даже при ошибке
        asyncio.run(_release_account_after_parsing(f"search:{keywords}", user_id, False, 0, str(e)))
        
        current_task.update_state(
            state="FAILURE",
            meta={"error": str(e), "keywords": keywords}
        )
        raise