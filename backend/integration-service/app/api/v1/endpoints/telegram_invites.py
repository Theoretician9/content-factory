"""
API endpoints для Telegram приглашений через Integration Service
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from telethon.errors import FloodWaitError, PeerFloodError, UserNotMutualContactError
# PrivacyRestrictedError не существует в этой версии telethon, используем общий Exception
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.messages import AddChatUserRequest
from typing import Dict, Any, Optional
from datetime import datetime
import asyncio
import logging

from app.core.database import get_db
from app.models.telegram_sessions import TelegramSession
from app.core.auth import get_current_user
from app.schemas.telegram_invites import (
    TelegramInviteRequest,
    TelegramInviteResponse,
    TelegramMessageRequest,
    TelegramMessageResponse,
    TelegramAccountLimitsResponse
)
from app.services.telegram_service import TelegramService

router = APIRouter()
logger = logging.getLogger(__name__)


def get_telegram_service() -> TelegramService:
    """Получение Telegram Service"""
    return TelegramService()


@router.post("/accounts/{account_id}/invite", response_model=TelegramInviteResponse)
async def send_telegram_invite(
    account_id: int,
    invite_data: TelegramInviteRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    telegram_service: TelegramService = Depends(get_telegram_service)
):
    """Отправка приглашения через Telegram аккаунт"""
    
    # Проверка доступа к аккаунту
    account = db.query(TelegramSession).filter(
        TelegramSession.id == account_id,
        TelegramSession.user_id == current_user.id
    ).first()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Telegram аккаунт {account_id} не найден или нет доступа"
        )
    
    if not account.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram аккаунт неактивен"
        )
    
    try:
        # Получение Telegram клиента
        client = await telegram_service.get_client(account)
        
        if not client.is_connected():
            await client.connect()
        
        start_time = datetime.utcnow()
        result = None
        error_details = None
        
        try:
            if invite_data.invite_type == "group_invite":
                # Приглашение в группу/канал
                if invite_data.group_id:
                    if invite_data.target_username:
                        # Приглашение по username
                        user = await client.get_entity(invite_data.target_username)
                        group = await client.get_entity(invite_data.group_id)
                        
                        if hasattr(group, 'megagroup') and group.megagroup:
                            # Супергруппа
                            result = await client(InviteToChannelRequest(
                                channel=group,
                                users=[user]
                            ))
                        else:
                            # Обычная группа
                            result = await client(AddChatUserRequest(
                                chat_id=group.id,
                                user_id=user.id,
                                fwd_limit=10
                            ))
                    
                    elif invite_data.target_phone:
                        # Приглашение по номеру телефона
                        contacts = await client.get_contacts()
                        user = None
                        
                        for contact in contacts:
                            if hasattr(contact, 'phone') and contact.phone == invite_data.target_phone.replace('+', ''):
                                user = contact
                                break
                        
                        if not user:
                            raise Exception(f"Контакт с номером {invite_data.target_phone} не найден")
                        
                        group = await client.get_entity(invite_data.group_id)
                        result = await client(InviteToChannelRequest(
                            channel=group,
                            users=[user]
                        ))
                
                else:
                    raise Exception("group_id обязателен для group_invite")
            
            elif invite_data.invite_type == "direct_message":
                # Прямое сообщение
                target_entity = invite_data.target_username or invite_data.target_phone
                
                if not target_entity:
                    raise Exception("Необходим target_username или target_phone для direct_message")
                
                if not invite_data.message:
                    raise Exception("Сообщение обязательно для direct_message")
                
                # Отправка сообщения
                result = await client.send_message(
                    entity=target_entity,
                    message=invite_data.message
                )
            
            else:
                raise Exception(f"Неподдерживаемый тип приглашения: {invite_data.invite_type}")
        
        except FloodWaitError as e:
            # Telegram FloodWait ошибка
            logger.warning(f"FloodWait для аккаунта {account_id}: {e.seconds}s")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "flood_wait",
                    "seconds": e.seconds,
                    "message": f"Превышен лимит запросов. Ожидание {e.seconds} секунд."
                }
            )
        
        except PrivacyRestrictedError as e:
            # Настройки приватности пользователя
            logger.info(f"Privacy restricted для {invite_data.target_username or invite_data.target_phone}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "privacy_restricted",
                    "message": "Настройки приватности пользователя запрещают приглашения"
                }
            )
        
        except PeerFloodError as e:
            # Слишком много запросов к пользователям
            logger.warning(f"PeerFlood для аккаунта {account_id}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "peer_flood",
                    "message": "Слишком много запросов к пользователям. Аккаунт временно заблокирован."
                }
            )
        
        except UserNotMutualContactError as e:
            # Пользователь не в контактах
            logger.info(f"User not mutual contact: {invite_data.target_username or invite_data.target_phone}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "not_mutual_contact",
                    "message": "Пользователь должен быть в ваших контактах"
                }
            )
        
        except Exception as e:
            # Общие ошибки
            logger.error(f"Telegram invite error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invite_failed",
                    "message": str(e)
                }
            )
        
        # Успешный результат
        end_time = datetime.utcnow()
        execution_time = (end_time - start_time).total_seconds()
        
        return TelegramInviteResponse(
            status="success",
            message_id=result.id if hasattr(result, 'id') else None,
            sent_at=end_time,
            execution_time=execution_time,
            target_username=invite_data.target_username,
            target_phone=invite_data.target_phone,
            invite_type=invite_data.invite_type
        )
    
    except HTTPException:
        # Перебрасываем HTTP исключения как есть
        raise
    
    except Exception as e:
        logger.error(f"Unexpected error in send_telegram_invite: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка: {str(e)}"
        )


@router.post("/accounts/{account_id}/message", response_model=TelegramMessageResponse)
async def send_telegram_message(
    account_id: int,
    message_data: TelegramMessageRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    telegram_service: TelegramService = Depends(get_telegram_service)
):
    """Отправка сообщения через Telegram аккаунт"""
    
    # Проверка доступа к аккаунту
    account = db.query(TelegramSession).filter(
        TelegramSession.id == account_id,
        TelegramSession.user_id == current_user.id
    ).first()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Telegram аккаунт {account_id} не найден"
        )
    
    try:
        client = await telegram_service.get_client(account)
        
        if not client.is_connected():
            await client.connect()
        
        start_time = datetime.utcnow()
        
        # Отправка сообщения
        result = await client.send_message(
            entity=message_data.target_entity,
            message=message_data.message,
            parse_mode='html' if message_data.parse_mode == 'html' else None
        )
        
        end_time = datetime.utcnow()
        execution_time = (end_time - start_time).total_seconds()
        
        return TelegramMessageResponse(
            status="success",
            message_id=result.id,
            sent_at=end_time,
            execution_time=execution_time,
            target_entity=message_data.target_entity
        )
    
    except FloodWaitError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "flood_wait",
                "seconds": e.seconds
            }
        )
    
    except Exception as e:
        logger.error(f"Message send error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка отправки сообщения: {str(e)}"
        )


@router.get("/accounts/{account_id}/limits", response_model=TelegramAccountLimitsResponse)
async def get_account_limits(
    account_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение информации о лимитах аккаунта"""
    
    account = db.query(TelegramSession).filter(
        TelegramSession.id == account_id,
        TelegramSession.user_id == current_user.id
    ).first()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Telegram аккаунт {account_id} не найден"
        )
    
    # Базовые лимиты Telegram
    limits = {
        "daily_invites": 50,      # Приглашений в день
        "daily_messages": 40,     # Сообщений в день
        "hourly_invites": 5,      # Приглашений в час
        "flood_wait_active": False,
        "account_restrictions": []
    }
    
    # TODO: Интеграция с Redis для получения текущих счетчиков
    # TODO: Проверка активных flood wait ограничений
    
    return TelegramAccountLimitsResponse(
        account_id=account_id,
        limits=limits,
        current_usage={
            "daily_invites_used": 0,
            "daily_messages_used": 0,
            "hourly_invites_used": 0
        },
        restrictions=[],
        last_updated=datetime.utcnow()
    )


@router.get("/accounts")
async def get_user_telegram_accounts(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение всех Telegram аккаунтов пользователя для Invite Service"""
    
    accounts = db.query(TelegramSession).filter(
        TelegramSession.user_id == current_user.id,
        TelegramSession.is_active == True
    ).all()
    
    return [
        {
            "id": acc.id,
            "username": acc.username,
            "phone": acc.phone,
            "first_name": acc.first_name,
            "last_name": acc.last_name,
            "status": "active" if acc.is_active else "inactive",
            "created_at": acc.created_at,
            "last_activity": acc.updated_at,
            "daily_limits": {
                "invites": 50,
                "messages": 40
            }
        }
        for acc in accounts
    ] 