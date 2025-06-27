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
@router.get("")
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
        
        # Get active account for this platform (using same method as parsing)
        integration_client = get_integration_client()
        
        # Use the same method that works in parsing - get all active accounts
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{integration_client.base_url}/api/v1/telegram/internal/active-accounts"
                )
                
                if response.status_code == 200:
                    all_accounts = response.json()
                    logger.info(f"✅ Retrieved {len(all_accounts)} accounts from internal endpoint")
                    
                    # DEBUG: Логируем для диагностики
                    logger.info(f"🔍 DEBUG: Current JWT user_id: {user_id} (type: {type(user_id)})")
                    for i, acc in enumerate(all_accounts[:3]):  # Только первые 3 для краткости
                        acc_user_id = acc.get('user_id')
                        logger.info(f"🔍 DEBUG: Account {i}: user_id={acc_user_id} (type: {type(acc_user_id)})")
                    
                    # Filter accounts for this user
                    user_accounts = [acc for acc in all_accounts if acc.get('user_id') == user_id]
                    
                    logger.info(f"🔍 DEBUG: After filtering: found {len(user_accounts)} accounts for user_id {user_id}")
                    
                    if not user_accounts:
                        raise HTTPException(503, f"No active Telegram accounts available for user {user_id}")
                    
                    # Select the first available account
                    selected_account = user_accounts[0]
                    session_id = selected_account.get('session_id') or selected_account.get('id')
                    
                    logger.info(f"🔑 Using Telegram account {session_id} for search")
                    
                    # Get credentials (same structure as parsing)
                    credentials = {
                        'session_id': session_id,
                        'api_id': selected_account.get('api_id'),
                        'api_hash': selected_account.get('api_hash'),
                        'session_data': selected_account.get('session_data')
                    }
                    
                    if not credentials['session_data']:
                        raise HTTPException(503, f"No session data available for account {session_id}")
                        
                else:
                    logger.error(f"❌ Failed to get accounts from internal endpoint: {response.status_code}")
                    raise HTTPException(503, "Integration service unavailable")
                    
        except httpx.RequestError as e:
            logger.error(f"❌ Network error getting accounts: {e}")
            raise HTTPException(503, "Integration service unavailable")
        
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