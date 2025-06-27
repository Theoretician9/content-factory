from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID
import logging
import os

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
from ....core.auth import get_user_id_from_request
from ....core.vault import get_vault_client

router = APIRouter()
logger = logging.getLogger(__name__)

# Зависимости
async def get_telegram_service() -> TelegramService:
    return TelegramService()

async def get_log_service() -> IntegrationLogService:
    return IntegrationLogService()

@router.post("/connect", response_model=TelegramConnectResponse)
async def connect_telegram_account(
    request: Request,
    auth_request: TelegramAuthRequest,
    session: AsyncSession = Depends(get_async_session),
    telegram_service: TelegramService = Depends(get_telegram_service)
):
    """
    Подключение Telegram аккаунта с изоляцией пользователей.
    
    Поддерживает:
    - SMS код (code: str)
    - 2FA пароль (password: str)
    - QR-код авторизацию
    """
    try:
        # Изоляция пользователей
        user_id = await get_user_id_from_request(request)
        
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
    request: Request,
    telegram_service: TelegramService = Depends(get_telegram_service)
):
    """Получение QR кода для авторизации через Telegram приложение"""
    try:
        # Изоляция пользователей
        user_id = await get_user_id_from_request(request)
        
        qr_code = await telegram_service.generate_qr_code(user_id)
        return {"qr_code": qr_code, "message": "Отсканируйте QR код в Telegram приложении"}
    except Exception as e:
        logger.error(f"Error generating QR code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка генерации QR кода: {str(e)}"
        )

@router.post("/qr-check", response_model=TelegramConnectResponse)
async def check_qr_authorization(
    request: Request,
    qr_request: Optional[dict] = None,  # Принимаем опциональный request body
    session: AsyncSession = Depends(get_async_session),
    telegram_service: TelegramService = Depends(get_telegram_service)
):
    """
    Проверка авторизации по QR коду с полной поддержкой 2FA.
    
    Поддерживает:
    - Обычная проверка QR: POST /qr-check (без body)
    - QR + 2FA пароль: POST /qr-check {"password": "your_2fa_password"}
    """
    try:
        # Изоляция пользователей
        user_id = await get_user_id_from_request(request)
        
        # Извлекаем пароль из request body если передан
        password = None
        if qr_request and isinstance(qr_request, dict):
            password = qr_request.get('password')
            if password:
                logger.info(f"🔐 QR check with 2FA password for user {user_id}")
        
        # Передаем пароль в сервис
        result = await telegram_service.check_qr_authorization(session, user_id, password)
        return result
    except Exception as e:
        logger.error(f"Error checking QR authorization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка проверки QR авторизации: {str(e)}"
        )

@router.get("/accounts", response_model=List[TelegramSessionResponse])
async def get_telegram_accounts(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    telegram_service: TelegramService = Depends(get_telegram_service),
    active_only: bool = Query(True, description="Только активные аккаунты")
):
    """Получение списка подключенных Telegram аккаунтов с изоляцией пользователей"""
    try:
        # Изоляция пользователей
        user_id = await get_user_id_from_request(request)
        
        # Информационное логирование
        logger.info(f"🔍 GET /accounts - User ID: {user_id}, active_only: {active_only}")
        sessions = await telegram_service.get_user_sessions(session, user_id, active_only)
        logger.info(f"📋 Found {len(sessions)} sessions for user {user_id}")
        
        # КРИТИЧЕСКАЯ ПРОВЕРКА БЕЗОПАСНОСТИ: фильтруем сессии еще раз
        filtered_sessions = [s for s in sessions if s.user_id == user_id]
        
        logger.info(f"🔒 Security check: filtered {len(sessions)} → {len(filtered_sessions)} sessions for user {user_id}")
        
        if len(sessions) != len(filtered_sessions):
            logger.error(f"🚨 SECURITY BREACH: Found sessions with wrong user_id for requesting user {user_id}!")
            for s in sessions:
                if s.user_id != user_id:
                    logger.error(f"🚨 Wrong session: {s.id} has user_id={s.user_id}, expected {user_id}")
        
        result = [
            TelegramSessionResponse(
                id=s.id,
                created_at=s.created_at,
                updated_at=s.updated_at,
                user_id=s.user_id,
                phone=s.phone,
                session_metadata=s.session_metadata,
                is_active=s.is_active
            )
            for s in filtered_sessions  # Используем отфильтрованный список
        ]
        
        # Логируем что возвращаем только данные текущего пользователя
        for r in result:
            logger.info(f"📱 Returning session {r.id} with user_id={r.user_id} for requesting user {user_id}")
        
        return result
    except Exception as e:
        logger.error(f"Error getting accounts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения аккаунтов: {str(e)}"
        )

@router.get("/accounts/{session_id}", response_model=TelegramSessionResponse)
async def get_telegram_account(
    request: Request,
    session_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    telegram_service: TelegramService = Depends(get_telegram_service)
):
    """Получение информации о конкретном Telegram аккаунте с изоляцией пользователей"""
    try:
        # Изоляция пользователей
        user_id = await get_user_id_from_request(request)
        
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
    request: Request,
    session_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    telegram_service: TelegramService = Depends(get_telegram_service)
):
    """Отключение Telegram аккаунта с изоляцией пользователей"""
    try:
        # Изоляция пользователей
        user_id = await get_user_id_from_request(request)
        
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
    request: Request,
    session_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    telegram_service: TelegramService = Depends(get_telegram_service)
):
    """Переподключение Telegram аккаунта с изоляцией пользователей"""
    try:
        # Изоляция пользователей
        user_id = await get_user_id_from_request(request)
        
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

@router.get("/test-auth")
async def test_auth(request: Request):
    """Тестовый endpoint для проверки работы авторизации"""
    try:
        # Изоляция пользователей
        user_id = await get_user_id_from_request(request)
        
        logger.info(f"🔐 TEST-AUTH: Successfully authenticated user_id = {user_id}")
        return {"authenticated_user_id": user_id, "message": "Authentication working!"}
    except Exception as e:
        logger.error(f"🚨 TEST-AUTH ERROR: {e}")
        return {"error": str(e), "message": "Authentication failed"}

@router.get("/test-public")
async def test_public():
    """Публичный тестовый endpoint для проверки работы сервиса"""
    return {"status": "ok", "message": "Integration Service is working!", "service": "integration-service"}

@router.get("/logs", response_model=List[IntegrationLogResponse])
async def get_integration_logs(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    log_service: IntegrationLogService = Depends(get_log_service),
    integration_type: Optional[str] = Query("telegram", description="Тип интеграции"),
    log_status: Optional[str] = Query(None, description="Статус: success, error, pending"),
    days_back: int = Query(30, ge=1, le=365, description="Количество дней назад"),
    pagination: PaginationParams = Depends()
):
    """Получение логов интеграций пользователя с изоляцией"""
    try:
        # Изоляция пользователей
        user_id = await get_user_id_from_request(request)
        
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
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    log_service: IntegrationLogService = Depends(get_log_service),
    days_back: int = Query(7, ge=1, le=30, description="Количество дней назад")
):
    """Получение статистики ошибок для пользователя с изоляцией"""
    try:
        # Изоляция пользователей
        user_id = await get_user_id_from_request(request)
        
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

# Internal endpoint for parsing-service (no auth required)
@router.get("/internal/active-accounts")
async def get_active_accounts_internal(
    session: AsyncSession = Depends(get_async_session),
    telegram_service: TelegramService = Depends(get_telegram_service)
):
    """
    Internal endpoint для получения всех активных Telegram аккаунтов с полными данными для подключения.
    Используется parsing-service для реального парсинга.
    БЕЗ АВТОРИЗАЦИИ - только для внутренних сервисов!
    """
    try:
        logger.info("🔧 Internal request: getting all active Telegram accounts with full credentials for parsing service")
        
        # Получаем все активные сессии без фильтрации по пользователю
        all_sessions = await telegram_service.session_service.get_all_active(session)
        
        # Получаем API ключи из Vault
        vault_client = get_vault_client()
        
        try:
            # Получаем Telegram API ключи из Vault
            logger.info("🔑 Trying to get Telegram API credentials from Vault...")
            telegram_config = vault_client.get_secret("integration-service")
            logger.info(f"🔑 Vault response: {telegram_config}")
            api_id = telegram_config.get('telegram_api_id')
            api_hash = telegram_config.get('telegram_api_hash')
            logger.info(f"🔑 Got from Vault: api_id={api_id}, api_hash={'***' if api_hash else None}")
        except Exception as e:
            logger.error(f"❌ Vault error, using fallback credentials: {e}")
            # Fallback на переменные окружения
            api_id = os.getenv('TELEGRAM_API_ID')
            api_hash = os.getenv('TELEGRAM_API_HASH')
            logger.info(f"🔑 Got from ENV: api_id={api_id}, api_hash={'***' if api_hash else None}")
        
        # КРИТИЧЕСКАЯ ПРОВЕРКА: логируем финальные значения credentials
        logger.info(f"🔍 FINAL CREDENTIALS CHECK: api_id={api_id}, api_hash={'***' if api_hash else None}")
        
        if not api_id or not api_hash:
            logger.error(f"❌ CRITICAL: Missing API credentials! api_id={api_id}, api_hash={api_hash}")
        
        result = []
        for s in all_sessions:
            try:
                # Session данные берем из БД, а не из Vault!
                session_data = s.session_data if hasattr(s, 'session_data') and s.session_data else None
                
                account_data = {
                    "id": str(s.id),
                    "user_id": s.user_id,
                    "phone": s.phone,
                    "is_active": s.is_active,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    # Добавляем данные для подключения
                    "api_id": api_id,
                    "api_hash": api_hash,
                    "session_id": str(s.id),
                    "session_data": session_data,  # Session данные из БД
                    "connection_ready": session_data is not None
                }
                
                # КРИТИЧЕСКОЕ ЛОГИРОВАНИЕ: проверяем что передаем в parsing-service
                logger.info(f"📤 Account {s.id}: api_id={account_data['api_id']}, api_hash={'***' if account_data['api_hash'] else None}, has_session_data={account_data['connection_ready']}")
                
                result.append(account_data)
                
            except Exception as account_error:
                logger.error(f"❌ Error processing account {s.id}: {account_error}")
                continue
        
        logger.info(f"🔧 Returning {len(result)} active accounts with full credentials for parsing service")
        logger.info(f"📊 Accounts with session data: {len([a for a in result if a['connection_ready']])}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting active accounts for parsing service: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения активных аккаунтов: {str(e)}"
        ) 