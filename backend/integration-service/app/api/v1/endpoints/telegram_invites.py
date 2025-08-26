"""
API endpoints для Telegram приглашений через Integration Service
Теперь использует Account Manager для распределения аккаунтов
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from telethon.errors import FloodWaitError, PeerFloodError, UserNotMutualContactError
# Убрал PrivacyRestrictedError - не существует в этой версии telethon
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.messages import AddChatUserRequest
from typing import Dict, Any, Optional
from datetime import datetime
from uuid import UUID
import asyncio
import logging

# ИСПРАВЛЕННЫЕ ИМПОРТЫ в соответствии с реальной структурой
from ....database import get_async_session
from ....models.telegram_sessions import TelegramSession
from ....models.account_manager_types import AccountPurpose, ActionType, ErrorType, AccountUsageStats
from ....core.auth import get_user_id_from_request
from ....schemas.telegram_invites import (
    TelegramInviteRequest,
    TelegramInviteResponse,
    TelegramMessageRequest,
    TelegramMessageResponse,
    TelegramAccountLimitsResponse
)
from ....services.telegram_service import TelegramService
from ....services.account_manager import AccountManagerService

router = APIRouter()
logger = logging.getLogger(__name__)


def get_telegram_service() -> TelegramService:
    """Получение Telegram Service"""
    return TelegramService()

def get_account_manager() -> AccountManagerService:
    """Получение Account Manager Service"""
    return AccountManagerService()


@router.post("/accounts/{account_id}/check-admin")
async def check_account_admin_rights(
    account_id: UUID,
    check_data: dict,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    telegram_service: TelegramService = Depends(get_telegram_service)
):
    """Проверка административных прав аккаунта в группе/канале"""
    
    # Изоляция пользователей
    user_id = await get_user_id_from_request(request)
    
    # Получаем аккаунт и проверяем принадлежность пользователю
    result = await session.execute(
        select(TelegramSession).where(
            TelegramSession.id == account_id,
            TelegramSession.user_id == user_id
        )
    )
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Telegram аккаунт не найден или нет доступа"
        )
    
    group_id = check_data.get("group_id")
    required_permissions = check_data.get("required_permissions", [])
    
    if not group_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="group_id обязателен"
        )
    
    try:
        # Получение Telegram клиента
        client = await telegram_service.get_client(account)
        
        if not client.is_connected():
            await client.connect()
        
        # Получаем информацию о группе/канале
        try:
            group = await client.get_entity(group_id)
        except Exception as e:
            logger.error(f"Ошибка получения группы {group_id}: {str(e)}")
            return {
                "is_admin": False,
                "permissions": [],
                "error": f"Не удалось получить информацию о группе: {str(e)}"
            }
        
        # Получаем свои права в этой группе
        try:
            # Получаем текущего пользователя (себя)
            me = await client.get_me()
            
            # Получаем список администраторов
            admins = await client.get_participants(group, filter=lambda p: p.participant)
            
            my_admin_rights = None
            is_admin = False
            
            # Ищем себя в списке админов
            for participant in admins:
                if hasattr(participant, 'user_id') and participant.user_id == me.id:
                    if hasattr(participant, 'admin_rights') and participant.admin_rights:
                        my_admin_rights = participant.admin_rights
                        is_admin = True
                        break
                    elif hasattr(participant, 'creator') and participant.creator:
                        # Креатор имеет все права
                        is_admin = True
                        my_admin_rights = type('AdminRights', (), {
                            'invite_users': True,
                            'add_admins': True,
                            'ban_users': True,
                            'delete_messages': True,
                            'edit_messages': True,
                            'post_messages': True,
                            'pin_messages': True
                        })()
                        break
            
            if not is_admin:
                logger.info(f"Аккаунт {account_id} не является администратором в группе {group_id}")
                return {
                    "is_admin": False,
                    "permissions": [],
                    "message": "Не является администратором"
                }
            
            # Определяем конкретные права
            permissions = []
            
            if hasattr(my_admin_rights, 'invite_users') and my_admin_rights.invite_users:
                permissions.append('invite_users')
            
            if hasattr(my_admin_rights, 'add_admins') and my_admin_rights.add_admins:
                permissions.append('add_admins')
            
            if hasattr(my_admin_rights, 'ban_users') and my_admin_rights.ban_users:
                permissions.append('ban_users')
            
            if hasattr(my_admin_rights, 'delete_messages') and my_admin_rights.delete_messages:
                permissions.append('delete_messages')
            
            if hasattr(my_admin_rights, 'post_messages') and my_admin_rights.post_messages:
                permissions.append('post_messages')
            
            # Проверяем наличие требуемых прав
            has_required_permissions = all(perm in permissions for perm in required_permissions)
            
            logger.info(f"✅ Аккаунт {account_id} - админ: {is_admin}, права: {permissions}")
            
            return {
                "is_admin": is_admin,
                "permissions": permissions,
                "has_required_permissions": has_required_permissions,
                "group_title": getattr(group, 'title', str(group_id)),
                "message": f"Аккаунт {'\u044f\u0432\u043b\u044f\u0435\u0442\u0441\u044f' if is_admin else '\u043d\u0435 \u044f\u0432\u043b\u044f\u0435\u0442\u0441\u044f'} администратором"
            }
            
        except Exception as e:
            logger.error(f"Ошибка проверки админ прав для {account_id} в {group_id}: {str(e)}")
            return {
                "is_admin": False,
                "permissions": [],
                "error": f"Ошибка проверки прав: {str(e)}"
            }
            
    except Exception as e:
        logger.error(f"Ошибка подключения к Telegram для аккаунта {account_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка подключения к Telegram: {str(e)}"
        )


@router.post("/accounts/{account_id}/invite", response_model=TelegramInviteResponse)
async def send_telegram_invite_by_account(
    account_id: UUID,
    invite_data: TelegramInviteRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    telegram_service: TelegramService = Depends(get_telegram_service)
):
    """Отправка приглашения через конкретный Telegram аккаунт - совместимость с Invite Service"""
    
    # Изоляция пользователей
    user_id = await get_user_id_from_request(request)
    
    # Получаем аккаунт и проверяем принадлежность пользователю
    result = await session.execute(
        select(TelegramSession).where(
            TelegramSession.id == account_id,
            TelegramSession.user_id == user_id
        )
    )
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Telegram аккаунт не найден или нет доступа"
        )
    
    try:
        # Получение Telegram клиента
        client = await telegram_service.get_client(account)
        
        if not client.is_connected():
            await client.connect()
        
        start_time = datetime.utcnow()
        result_data = None
        
        # Обработка разных типов приглашений
        if invite_data.invite_type == "group_invite":
            # Приглашение в группу/канал
            if not invite_data.group_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="group_id обязателен для group_invite"
                )
            
            if invite_data.target_username:
                # Приглашение по username
                user = await client.get_entity(invite_data.target_username)
                group = await client.get_entity(invite_data.group_id)
                
                if hasattr(group, 'megagroup') and group.megagroup:
                    # Супергруппа
                    result_data = await client(InviteToChannelRequest(
                        channel=group,
                        users=[user]
                    ))
                else:
                    # Обычная группа
                    result_data = await client(AddChatUserRequest(
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
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Контакт с номером {invite_data.target_phone} не найден"
                    )
                
                group = await client.get_entity(invite_data.group_id)
                result_data = await client(InviteToChannelRequest(
                    channel=group,
                    users=[user]
                ))
            
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Необходим target_username или target_phone"
                )
        
        elif invite_data.invite_type == "direct_message":
            # Прямое сообщение
            target_entity = invite_data.target_username or invite_data.target_phone
            
            if not target_entity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Необходим target_username или target_phone для direct_message"
                )
            
            if not invite_data.message:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Сообщение обязательно для direct_message"
                )
            
            # Отправка сообщения
            result_data = await client.send_message(
                entity=target_entity,
                message=invite_data.message
            )
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Неподдерживаемый тип приглашения: {invite_data.invite_type}"
            )
        
        # Успешный результат
        end_time = datetime.utcnow()
        execution_time = (end_time - start_time).total_seconds()
        
        return TelegramInviteResponse(
            success=True,
            message="Приглашение отправлено успешно",
            account_id=account_id,
            target_username=invite_data.target_username,
            target_phone=invite_data.target_phone,
            execution_time=execution_time,
            sent_at=end_time
        )
    
    except FloodWaitError as e:
        # Telegram FloodWait ошибка
        logger.warning(f"FloodWait для аккаунта {account_id}: {e.seconds}s")
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "flood_wait",
                "message": f"Необходимо подождать {e.seconds} секунд",
                "retry_after": e.seconds
            }
        )
    
    except PeerFloodError as e:
        # Слишком много запросов к одному пользователю
        logger.warning(f"PeerFlood для аккаунта {account_id}")
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "peer_flood",
                "message": "Слишком много запросов к пользователю. Попробуйте позже",
                "retry_after": 86400  # 24 часа
            }
        )
    
    except UserNotMutualContactError as e:
        # Пользователь не в контактах
        logger.info(f"User not mutual contact для {invite_data.target_username or invite_data.target_phone}")
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "user_not_mutual_contact",
                "message": "Пользователь не в списке взаимных контактов"
            }
        )
    
    except Exception as e:
        # Обработка других ошибок
        error_msg = str(e).lower()
        
        if "privacy" in error_msg or "restricted" in error_msg:
            logger.info(f"Privacy restricted для {invite_data.target_username or invite_data.target_phone}")
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "privacy_restricted",
                    "message": "Настройки приватности пользователя запрещают приглашения"
                }
            )
        
        # Общие ошибки
        logger.error(f"Telegram invite error для аккаунта {account_id}: {str(e)}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "invite_failed",
                "message": str(e)
            }
        )


@router.post("/invite", response_model=TelegramInviteResponse)
async def send_telegram_invite(
    invite_data: TelegramInviteRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    telegram_service: TelegramService = Depends(get_telegram_service),
    account_manager: AccountManagerService = Depends(get_account_manager)
):
    """Отправка приглашения через Account Manager - правильная архитектура"""
    
    # Изоляция пользователей  
    user_id = await get_user_id_from_request(request)
    
    # 1. Запросить аккаунт у Account Manager
    allocation = await account_manager.allocate_account(
        session=session,
        user_id=user_id,
        purpose=AccountPurpose.INVITATION,
        service_name="integration-service",
        timeout_minutes=30
    )
    
    if not allocation:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "no_available_accounts",
                "message": "Нет доступных Telegram аккаунтов для отправки приглашений"
            }
        )
    
    # 2. Получить TelegramSession по ID
    result = await session.execute(
        select(TelegramSession).where(TelegramSession.id == allocation.account_id)
    )
    account = result.scalar_one_or_none()
    
    if not account:
        # Освободить аллокацию при ошибке
        await account_manager.release_account(
            session=session,
            account_id=allocation.account_id,
            service_name="integration-service",
            usage_stats=AccountUsageStats(success=False, error_type=ErrorType.ACCOUNT_NOT_FOUND)
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Telegram аккаунт не найден"
        )
    
    usage_stats = AccountUsageStats(
        invites_sent=0,
        messages_sent=0,
        success=False
    )
    
    try:
        # 3. Получение Telegram клиента
        client = await telegram_service.get_client(account)
        
        if not client.is_connected():
            await client.connect()
        
        start_time = datetime.utcnow()
        result = None
        
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
                        
                        usage_stats.invites_sent = 1
                        usage_stats.channels_used = [str(invite_data.group_id)]
                    
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
                        
                        usage_stats.invites_sent = 1
                        usage_stats.channels_used = [str(invite_data.group_id)]
                
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
                
                usage_stats.messages_sent = 1
            
            else:
                raise Exception(f"Неподдерживаемый тип приглашения: {invite_data.invite_type}")
            
            # Успех!
            usage_stats.success = True
            
        except FloodWaitError as e:
            # Telegram FloodWait ошибка
            logger.warning(f"FloodWait для аккаунта {allocation.account_id}: {e.seconds}s")
            usage_stats.error_type = ErrorType.FLOOD_WAIT
            usage_stats.error_message = f"FloodWait {e.seconds}s"
            
            # Освободить аккаунт и обработать ошибку в Account Manager
            await account_manager.handle_account_error(
                session=session,
                account_id=allocation.account_id,
                error_type=ErrorType.FLOOD_WAIT,
                error_message=f"FloodWait {e.seconds}s",
                context={"service": "integration-service", "action": "invite"}
            )
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "flood_wait",
                    "seconds": e.seconds,
                    "message": f"Превышен лимит запросов. Ожидание {e.seconds} секунд."
                }
            )
        
        except PeerFloodError as e:
            # Слишком много запросов к пользователям
            logger.warning(f"PeerFlood для аккаунта {allocation.account_id}")
            usage_stats.error_type = ErrorType.PEER_FLOOD
            usage_stats.error_message = "PeerFlood - too many user requests"
            
            # Освободить аккаунт и обработать ошибку в Account Manager
            await account_manager.handle_account_error(
                session=session,
                account_id=allocation.account_id,
                error_type=ErrorType.PEER_FLOOD,
                error_message="Too many requests to users",
                context={"service": "integration-service", "action": "invite"}
            )
            
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
            usage_stats.error_type = ErrorType.USER_RESTRICTED
            usage_stats.error_message = "User not in contacts"
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "not_mutual_contact",
                    "message": "Пользователь должен быть в ваших контактах"
                }
            )
        
        except Exception as e:
            # Обработка ошибок приватности и других общих ошибок
            error_msg = str(e).lower()
            
            if "privacy" in error_msg or "restricted" in error_msg:
                logger.info(f"Privacy restricted для {invite_data.target_username or invite_data.target_phone}")
                usage_stats.error_type = ErrorType.USER_RESTRICTED
                usage_stats.error_message = "Privacy restrictions"
                
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "privacy_restricted",
                        "message": "Настройки приватности пользователя запрещают приглашения"
                    }
                )
            else:
                # Общие ошибки
                logger.error(f"Telegram invite error: {str(e)}")
                usage_stats.error_type = ErrorType.API_ERROR
                usage_stats.error_message = str(e)
                
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
            message="Приглашение успешно отправлено"
        )
        
    finally:
        # 4. ВСЕГДА освобождать аккаунт в Account Manager
        try:
            await account_manager.release_account(
                session=session,
                account_id=allocation.account_id,
                service_name="integration-service",
                usage_stats=usage_stats
            )
            logger.info(f"✅ Account {allocation.account_id} released successfully")
        except Exception as release_error:
            logger.error(f"❌ Failed to release account {allocation.account_id}: {release_error}")


@router.post("/accounts/{account_id}/message", response_model=TelegramMessageResponse)
async def send_telegram_message(
    account_id: UUID,
    message_data: TelegramMessageRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    telegram_service: TelegramService = Depends(get_telegram_service)
):
    """Отправка сообщения через Telegram аккаунт"""
    
    # Изоляция пользователей
    user_id = await get_user_id_from_request(request)
    
    # Проверка доступа к аккаунту
    account = await telegram_service.session_service.get_by_id(session, account_id)
    
    if not account or account.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Telegram аккаунт не найден"
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


@router.get("/accounts")
async def get_user_telegram_accounts(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    telegram_service: TelegramService = Depends(get_telegram_service)
):
    """Получение всех Telegram аккаунтов пользователя для Invite Service"""
    
    # Изоляция пользователей
    user_id = await get_user_id_from_request(request)
    
    accounts = await telegram_service.get_user_sessions(session, user_id, active_only=True)
    
    return [
        {
            "id": acc.id,
            "username": getattr(acc, 'username', None),
            "phone": acc.phone,
            "first_name": getattr(acc, 'first_name', None),
            "last_name": getattr(acc, 'last_name', None),
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


@router.get("/accounts/{account_id}/limits", response_model=TelegramAccountLimitsResponse)
async def get_account_limits(
    account_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    telegram_service: TelegramService = Depends(get_telegram_service)
):
    """Получение информации о лимитах аккаунта"""
    
    # Изоляция пользователей
    user_id = await get_user_id_from_request(request)
    
    # Получаем аккаунт и проверяем принадлежность пользователю
    account = await telegram_service.session_service.get_by_id(session, account_id)
    
    if not account or account.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Telegram аккаунт не найден"
        )
    
    # Базовые лимиты Telegram из базы данных
    limits = {
        "daily_invites": 30,      # Приглашений в день
        "daily_messages": 30,     # Сообщений в день
        "contacts_daily": 15,     # Контактов в день
        "per_channel_daily": 15,  # На канал в день
        "hourly_invites": 5,      # Приглашений в час
        "flood_wait_active": account.flood_wait_until is not None and account.flood_wait_until > datetime.utcnow(),
        "account_restrictions": []
    }
    
    # Текущее использование из базы данных
    current_usage = {
        "daily_invites_used": account.used_invites_today or 0,
        "daily_messages_used": account.used_messages_today or 0,
        "contacts_used": account.contacts_today or 0,
        "hourly_invites_used": 0  # TODO: из Redis
    }
    
    # Проверяем активные ограничения
    restrictions = []
    if account.blocked_until and account.blocked_until > datetime.utcnow():
        restrictions.append(f"Blocked until {account.blocked_until.isoformat()}")
    if account.flood_wait_until and account.flood_wait_until > datetime.utcnow():
        restrictions.append(f"Flood wait until {account.flood_wait_until.isoformat()}")
    
    return TelegramAccountLimitsResponse(
        account_id=account_id,
        limits=limits,
        current_usage=current_usage,
        restrictions=restrictions,
        last_updated=account.updated_at or datetime.utcnow()
    ) 