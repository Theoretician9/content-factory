"""
Search endpoints for multi-platform community search.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from typing import Optional, List, Dict, Any
import logging

from ....core.auth import get_user_id_from_request
from ....core.config import Platform, get_settings
from ....adapters.telegram import TelegramAdapter
from ....core.integration_client import get_integration_client

logger = logging.getLogger(__name__)
router = APIRouter()

settings = get_settings()


@router.get("/")
async def search_communities(
    request: Request,
    platform: str = Query(..., description="Platform to search (telegram, instagram, whatsapp)"),
    query: str = Query(..., min_length=1, description="Search query keywords"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of results")
):
    """
    Search for communities by keywords across different platforms.
    
    Returns filtered and sorted communities:
    - Telegram: Only open channels with comments OR open groups
    - Sorting: By member count descending (largest first)
    - Pagination: offset/limit based
    """
    
    # Get user_id from JWT token
    user_id = await get_user_id_from_request(request)
    logger.info(f"🔍 User {user_id} searching {platform} communities: '{query}' (offset={offset}, limit={limit})")
    
    try:
        # Validate platform
        if platform not in [p.value for p in Platform]:
            raise HTTPException(400, f"Unsupported platform: {platform}")
        
        # Currently only Telegram is implemented
        if platform != "telegram":
            raise HTTPException(501, f"Search not implemented for platform: {platform}")
        
        # Get active account for this platform
        integration_client = get_integration_client()
        accounts = await integration_client.get_active_telegram_accounts()
        
        if not accounts:
            raise HTTPException(503, "No active Telegram accounts available for search")
        
        # Select the first available account
        selected_account = accounts[0]
        session_id = selected_account.get('session_id')
        
        logger.info(f"🔑 Using Telegram account {session_id} for search")
        
        # Get credentials from integration service
        from ....core.vault import get_vault_client
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
            raise HTTPException(503, f"Failed to authenticate with Telegram account {session_id}")
        
        try:
            # Perform search
            search_results = await adapter.search_communities(
                query=query,
                offset=offset,
                limit=limit
            )
            
            # Ensure cleanup
            await adapter.cleanup()
            
            logger.info(f"✅ Search completed: {len(search_results.get('results', []))} results found")
            
            return search_results
            
        except Exception as search_error:
            await adapter.cleanup()
            logger.error(f"❌ Search failed: {search_error}")
            raise HTTPException(500, f"Search failed: {str(search_error)}")
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error in search: {e}")
        raise HTTPException(500, f"Internal server error: {str(e)}")


@router.get("/stats")
async def get_search_stats(
    request: Request,
    platform: Optional[str] = Query(None, description="Platform filter")
):
    """
    Get search statistics and metrics.
    """
    user_id = await get_user_id_from_request(request)
    
    # TODO: Implement search statistics
    # This could include:
    # - Total searches performed
    # - Most popular search queries
    # - Success rate by platform
    # - Average response time
    
    return {
        "message": "Search statistics will be available in future versions",
        "user_id": user_id,
        "platform_filter": platform
    } 