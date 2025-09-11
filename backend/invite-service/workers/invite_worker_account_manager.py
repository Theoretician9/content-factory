"""
Новая функция для отправки приглашений через Account Manager
Заменяет прямые вызовы Integration Service согласно ТЗ Account Manager
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models import InviteTarget, TargetStatus
from app.adapters.base import InviteResult, InviteResultStatus
from app.clients.account_manager_client import AccountManagerClient

logger = logging.getLogger(__name__)


async def _send_single_invite_via_account_manager(
    task,
    target: InviteTarget,
    account_allocation: Dict[str, Any],
    account_manager: AccountManagerClient,
    adapter,
    db: Session
) -> InviteResult:
    """
    ✅ НОВАЯ ФУНКЦИЯ: Отправка одиночного приглашения через Account Manager
    Заменяет прямые вызовы Integration Service согласно ТЗ Account Manager
    """
    start_time = datetime.utcnow()
    
    try:
        # Получаем данные аккаунта из выделения Account Manager
        account_data = account_allocation['allocation']
        account_id = account_data['account_id']
        
        logger.info(f"🔄 AccountManager: Отправка приглашения для цели {target.id} через аккаунт {account_id}")
        
        # Обновляем статус цели на IN_PROGRESS
        target.status = TargetStatus.IN_PROGRESS
        target.attempt_count += 1
        target.updated_at = datetime.utcnow()
        db.commit()
        
        # Подготавливаем данные цели для адаптера
        target_data = {}
        if target.username:
            target_data['username'] = target.username
        if target.phone_number:
            target_data['phone_number'] = target.phone_number
        if target.user_id_platform:
            target_data['user_id'] = target.user_id_platform
            
        # Подготавливаем данные приглашения
        invite_data = {
            'group_id': task.settings.get('group_id') if task.settings else None,
            'message': task.settings.get('message') if task.settings else None
        }
        
        logger.info(f"🔍 AccountManager: Данные для приглашения - target: {target_data}, invite: {invite_data}")
        
        # ✅ КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Используем аккаунт из Account Manager вместо прямого вызова
        # Account Manager уже проверил лимиты, статус, блокировки
        account_for_adapter = type('Account', (), {
            'account_id': account_id,
            'username': account_data.get('username'),
            'phone': account_data.get('phone'),
            'session_string': account_data.get('session_string'),
            'api_id': account_data.get('api_id'),
            'api_hash': account_data.get('api_hash')
        })()
        
        # Выполняем приглашение через адаптер с аккаунтом от Account Manager
        result = await adapter.send_invite(account_for_adapter, target_data, invite_data)
        
        # Обрабатываем результат
        if result.is_success:
            logger.info(f"✅ AccountManager: Успешное приглашение для цели {target.id} через аккаунт {account_id}")
            target.status = TargetStatus.COMPLETED
            target.completed_at = datetime.utcnow()
            target.error_message = None
        else:
            logger.warning(f"⚠️ AccountManager: Неудачное приглашение для цели {target.id}: {result.error_message}")
            target.status = TargetStatus.FAILED
            target.error_message = result.error_message
            
            # Уведомляем Account Manager об ошибке для корректировки лимитов/блокировок
            await account_manager.handle_error(
                account_id=account_id,
                error_type=result.error_message,
                context={
                    'target_id': target.id,
                    'task_id': task.id,
                    'action': 'invite'
                }
            )
        
        target.updated_at = datetime.utcnow()
        
        # Коммитим изменения с обработкой ошибок
        try:
            db.commit()
        except Exception as db_error:
            logger.error(f"❌ Ошибка сохранения в БД для цели {target.id}: {str(db_error)}")
            db.rollback()
            # Повторная попытка коммита
            try:
                target.updated_at = datetime.utcnow()
                db.commit()
            except Exception as retry_error:
                logger.error(f"❌ Повторная ошибка сохранения в БД для цели {target.id}: {str(retry_error)}")
                db.rollback()
        
        # Возвращаем результат с временем выполнения
        result.execution_time = (datetime.utcnow() - start_time).total_seconds()
        result.account_id = account_id
        
        return result
        
    except Exception as e:
        logger.error(f"❌ AccountManager: Ошибка при отправке приглашения для цели {target.id}: {str(e)}")
        
        # Обновляем цель как неудачную
        target.status = TargetStatus.FAILED
        target.error_message = str(e)
        target.updated_at = datetime.utcnow()
        
        try:
            db.commit()
        except Exception as db_error:
            logger.error(f"❌ Ошибка сохранения ошибки в БД для цели {target.id}: {str(db_error)}")
            db.rollback()
        
        # Уведомляем Account Manager об ошибке
        if account_allocation:
            try:
                await account_manager.handle_error(
                    account_id=account_allocation['allocation']['account_id'],
                    error_type=str(e),
                    context={
                        'target_id': target.id,
                        'task_id': task.id,
                        'action': 'invite',
                        'error': 'exception_during_invite'
                    }
                )
            except Exception as error_report_error:
                logger.error(f"❌ Ошибка при уведомлении Account Manager об ошибке: {str(error_report_error)}")
        
        # Возвращаем результат с ошибкой
        return InviteResult(
            status=InviteResultStatus.FAILED,
            error_message=str(e),
            account_id=account_allocation['allocation']['account_id'] if account_allocation else None,
            execution_time=(datetime.utcnow() - start_time).total_seconds(),
            can_retry=_is_retryable_single_error(e)
        )


def _is_retryable_single_error(error) -> bool:
    """
    Определяет, можно ли повторить операцию при данной ошибке
    """
    error_str = str(error).lower()
    
    # Ошибки, которые можно повторить
    retryable_errors = [
        'timeout',
        'connection',
        'network',
        'temporary',
        'rate limit',
        'flood wait'
    ]
    
    # Ошибки, которые нельзя повторить
    non_retryable_errors = [
        'peer flood',
        'user not found',
        'no user has username',
        'invalid user',
        'banned',
        'restricted'
    ]
    
    # Проверяем на неповторяемые ошибки
    for non_retryable in non_retryable_errors:
        if non_retryable in error_str:
            return False
    
    # Проверяем на повторяемые ошибки
    for retryable in retryable_errors:
        if retryable in error_str:
            return True
    
    # По умолчанию считаем ошибку повторяемой
    return True
