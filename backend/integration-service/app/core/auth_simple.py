from fastapi import Request, HTTPException, Depends
import logging

logger = logging.getLogger(__name__)

def get_user_id_from_request(request: Request) -> int:
    """
    Получает user_id из состояния запроса, установленного middleware.
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        logger.error("🚫 User ID not found in request state")
        raise HTTPException(status_code=401, detail="Authentication required")
    
    logger.info(f"✅ Retrieved user_id={user_id} from request state")
    return user_id

async def get_current_user_id_simple(request: Request) -> int:
    """
    Асинхронная версия получения user_id из request state.
    """
    return get_user_id_from_request(request) 