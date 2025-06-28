"""
API endpoints для работы с аккаунтами интеграций
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any
import httpx
import logging

from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


def get_current_user_id() -> int:
    """Получение ID текущего пользователя из JWT токена"""
    # TODO: Реализовать извлечение user_id из JWT токена
    return 1  # Заглушка


@router.get("/", response_model=List[Dict[str, Any]])
async def get_accounts(user_id: int = Depends(get_current_user_id)):
    """
    Получение списка доступных аккаунтов для invite-задач
    
    Запрашивает аккаунты из Integration Service
    """
    try:
        # Запрос к Integration Service за списком аккаунтов пользователя
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.INTEGRATION_SERVICE_URL}/api/v1/accounts",
                headers={"X-User-ID": str(user_id)},
                timeout=10.0
            )
            
            if response.status_code == 200:
                accounts_data = response.json()
                
                # Преобразуем данные в формат для invite-service
                formatted_accounts = []
                for account in accounts_data:
                    formatted_accounts.append({
                        "account_id": account.get("id", ""),
                        "platform": account.get("platform", "telegram"),
                        "username": account.get("username", ""),
                        "status": account.get("status", "active"),
                        "daily_invite_limit": account.get("daily_limit", 50),
                        "daily_invites_used": 0,  # TODO: получать реальную статистику
                        "flood_wait_until": None,
                        "last_used_at": account.get("last_used_at"),
                        "phone_number": account.get("phone_number", ""),
                        "is_active": account.get("is_active", True)
                    })
                
                return formatted_accounts
            else:
                logger.error(f"Error from Integration Service: {response.status_code}")
                # Возвращаем пустой список если Integration Service недоступен
                return []
                
    except httpx.RequestError as e:
        logger.error(f"Network error contacting Integration Service: {str(e)}")
        # Возвращаем пустой список если сервис недоступен
        return []
    except Exception as e:
        logger.error(f"Unexpected error getting accounts: {str(e)}")
        # Возвращаем пустой список при любых ошибках
        return []


@router.get("/{account_id}", response_model=Dict[str, Any])
async def get_account_details(
    account_id: str,
    user_id: int = Depends(get_current_user_id)
):
    """
    Получение детальной информации об аккаунте
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.INTEGRATION_SERVICE_URL}/api/v1/accounts/{account_id}",
                headers={"X-User-ID": str(user_id)},
                timeout=10.0
            )
            
            if response.status_code == 200:
                account_data = response.json()
                
                # Добавляем дополнительную информацию для invite-service
                account_data.update({
                    "daily_invite_limit": account_data.get("daily_limit", 50),
                    "daily_invites_used": 0,  # TODO: получать реальную статистику
                    "flood_wait_until": None,
                    "invite_statistics": {
                        "total_invites": 0,
                        "successful_invites": 0,
                        "failed_invites": 0,
                        "last_7_days": 0
                    }
                })
                
                return account_data
            elif response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Account {account_id} not found"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Integration Service unavailable"
                )
                
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cannot connect to Integration Service"
        )


@router.get("/{account_id}/stats", response_model=Dict[str, Any])
async def get_account_invite_stats(
    account_id: str,
    user_id: int = Depends(get_current_user_id)
):
    """
    Получение статистики приглашений для аккаунта
    """
    # TODO: Реализовать получение реальной статистики из БД
    
    return {
        "account_id": account_id,
        "total_invites": 0,
        "successful_invites": 0,
        "failed_invites": 0,
        "rate_limited": 0,
        "flood_wait_events": 0,
        "daily_usage": {
            "today": 0,
            "limit": 50,
            "remaining": 50
        },
        "last_30_days": {
            "total": 0,
            "successful": 0,
            "failed": 0,
            "daily_breakdown": []
        },
        "last_activity": None,
        "status": "active"
    } 