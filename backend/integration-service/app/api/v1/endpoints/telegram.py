from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID
import logging

from ....database import get_async_session
from ....services.telegram_service import TelegramService
from ....services.integration_log_service import IntegrationLogService
from ....schemas.telegram import (
    TelegramAuthRequest,
    TelegramConnectResponse,
    TelegramSessionResponse,
    TelegramBotCreate,
    TelegramBotResponse,
    TelegramChannelCreate,
    TelegramChannelResponse,
    SendMessageRequest,
    SendMessageResponse
)
from ....schemas.base import BaseResponse, ErrorResponse, PaginationParams
from ....schemas.integration_logs import IntegrationLogResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# Зависимости
async def get_telegram_service() -> TelegramService:
    return TelegramService()

async def get_log_service() -> IntegrationLogService:
    return IntegrationLogService()

# Временная заглушка для получения user_id из токена
# В реальной реализации это будет через JWT токен
async def get_current_user_id() -> int:
    # TODO: Интегрировать с системой авторизации
    return 1

@router.post("/connect", response_model=TelegramConnectResponse)
async def connect_telegram_account(
    auth_request: TelegramAuthRequest,
    session: AsyncSession = Depends(get_async_session),
    telegram_service: TelegramService = Depends(get_telegram_service),
    user_id: int = Depends(get_current_user_id)
):
    """
    Подключение Telegram аккаунта.
    
    Поддерживает:
    - SMS код (code: str)
    - 2FA пароль (password: str)
    - QR-код авторизацию
    """
    try:
        result = await telegram_service.connect_account(session, user_id, auth_request)
        return result
    except Exception as e:
        logger.error(f"Error in connect endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка подключения аккаунта: {str(e)}"
        )

@router.get("/qr-code")
async def get_qr_code(
    telegram_service: TelegramService = Depends(get_telegram_service),
    user_id: int = Depends(get_current_user_id)
):
    """Получение QR кода для авторизации через Telegram приложение"""
    try:
        qr_code = await telegram_service.generate_qr_code(user_id)
        return {"qr_code": qr_code, "message": "Отсканируйте QR код в Telegram приложении"}
    except Exception as e:
        logger.error(f"Error generating QR code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка генерации QR кода: {str(e)}"
        )

@router.get("/accounts", response_model=List[TelegramSessionResponse])
async def get_telegram_accounts(
    session: AsyncSession = Depends(get_async_session),
    telegram_service: TelegramService = Depends(get_telegram_service),
    user_id: int = Depends(get_current_user_id),
    active_only: bool = Query(True, description="Только активные аккаунты")
):
    """Получение списка подключенных Telegram аккаунтов"""
    try:
        sessions = await telegram_service.get_user_sessions(session, user_id, active_only)
        return [
            TelegramSessionResponse(
                id=s.id,
                created_at=s.created_at,
                updated_at=s.updated_at,
                user_id=s.user_id,
                phone=s.phone,
                session_metadata=s.session_metadata,
                is_active=s.is_active
            )
            for s in sessions
        ]
    except Exception as e:
        logger.error(f"Error getting accounts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения аккаунтов: {str(e)}"
        )

@router.get("/accounts/{session_id}", response_model=TelegramSessionResponse)
async def get_telegram_account(
    session_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    telegram_service: TelegramService = Depends(get_telegram_service),
    user_id: int = Depends(get_current_user_id)
):
    """Получение информации о конкретном Telegram аккаунте"""
    try:
        telegram_session = await telegram_service.session_service.get_by_id(session, session_id)
        
        if not telegram_session or telegram_session.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Аккаунт не найден"
            )
        
        return TelegramSessionResponse(
            id=telegram_session.id,
            created_at=telegram_session.created_at,
            updated_at=telegram_session.updated_at,
            user_id=telegram_session.user_id,
            phone=telegram_session.phone,
            session_metadata=telegram_session.session_metadata,
            is_active=telegram_session.is_active
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting account: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения аккаунта: {str(e)}"
        )

@router.delete("/accounts/{session_id}", response_model=BaseResponse)
async def disconnect_telegram_account(
    session_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    telegram_service: TelegramService = Depends(get_telegram_service),
    user_id: int = Depends(get_current_user_id)
):
    """Отключение Telegram аккаунта"""
    try:
        success = await telegram_service.disconnect_session(session, user_id, session_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Аккаунт не найден или уже отключен"
            )
        
        return BaseResponse(message="Аккаунт успешно отключен")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disconnecting account: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отключения аккаунта: {str(e)}"
        )

@router.post("/accounts/{session_id}/reconnect", response_model=BaseResponse)
async def reconnect_telegram_account(
    session_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    telegram_service: TelegramService = Depends(get_telegram_service),
    user_id: int = Depends(get_current_user_id)
):
    """Переподключение Telegram аккаунта"""
    try:
        # Получаем сессию
        telegram_session = await telegram_service.session_service.get_by_id(session, session_id)
        
        if not telegram_session or telegram_session.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Аккаунт не найден"
            )
        
        # Активируем сессию
        await telegram_service.session_service.update(
            session, session_id, {"is_active": True}
        )
        
        return BaseResponse(message="Аккаунт успешно переподключен")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reconnecting account: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка переподключения аккаунта: {str(e)}"
        )

# TODO: Добавить endpoints для ботов и каналов
# @router.post("/bots", response_model=TelegramBotResponse)
# @router.get("/bots", response_model=List[TelegramBotResponse])
# @router.delete("/bots/{bot_id}")
# @router.post("/channels", response_model=TelegramChannelResponse)
# @router.get("/channels", response_model=List[TelegramChannelResponse])
# @router.delete("/channels/{channel_id}")
# @router.post("/channels/{channel_id}/send", response_model=SendMessageResponse)

@router.get("/logs", response_model=List[IntegrationLogResponse])
async def get_integration_logs(
    session: AsyncSession = Depends(get_async_session),
    log_service: IntegrationLogService = Depends(get_log_service),
    user_id: int = Depends(get_current_user_id),
    integration_type: Optional[str] = Query("telegram", description="Тип интеграции"),
    log_status: Optional[str] = Query(None, description="Статус: success, error, pending"),
    days_back: int = Query(30, ge=1, le=365, description="Количество дней назад"),
    pagination: PaginationParams = Depends()
):
    """Получение логов интеграций пользователя"""
    try:
        offset = (pagination.page - 1) * pagination.size
        
        logs = await log_service.get_user_logs(
            session=session,
            user_id=user_id,
            integration_type=integration_type,
            status=log_status,
            days_back=days_back,
            offset=offset,
            limit=pagination.size
        )
        
        return [
            IntegrationLogResponse(
                id=log.id,
                created_at=log.created_at,
                updated_at=log.updated_at,
                user_id=log.user_id,
                integration_type=log.integration_type,
                action=log.action,
                status=log.status,
                details=log.details,
                error_message=log.error_message
            )
            for log in logs
        ]
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения логов: {str(e)}"
        )

@router.get("/stats/errors")
async def get_error_stats(
    session: AsyncSession = Depends(get_async_session),
    log_service: IntegrationLogService = Depends(get_log_service),
    user_id: int = Depends(get_current_user_id),
    days_back: int = Query(7, ge=1, le=30, description="Количество дней назад")
):
    """Получение статистики ошибок для пользователя"""
    try:
        stats = await log_service.get_error_stats(
            session=session,
            user_id=user_id,
            integration_type="telegram",
            days_back=days_back
        )
        
        return stats
    except Exception as e:
        logger.error(f"Error getting error stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики: {str(e)}"
        ) 