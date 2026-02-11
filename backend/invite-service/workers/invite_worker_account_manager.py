"""
Новая функция для отправки приглашений через Account Manager
Заменяет прямые вызовы Integration Service согласно ТЗ Account Manager
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models import InviteTarget, TargetStatus
from app.models.invite_execution_log import InviteExecutionLog, LogLevel, ActionType
from app.adapters.base import InviteResult, InviteResultStatus
from app.clients.account_manager_client import AccountManagerClient

logger = logging.getLogger(__name__)


def _map_error_type_for_am(message: str) -> Optional[str]:
    """Преобразует текст ошибки адаптера/исключения в допустимый enum Account Manager.
    Возвращает None, если тип неизвестен и репортить в AM не нужно (чтобы избежать 422).
    """
    if not message:
        return None
    m = str(message).lower()
    if "flood wait" in m or "flood_wait" in m:
        return "flood_wait"
    if "peer flood" in m or "peer_flood" in m:
        return "peer_flood"
    if "deactivated" in m or "inputuserdeactivated" in m:
        return "deactivated"
    if "auth" in m and "key" in m:
        return "auth_key"
    if "blocked" in m or "ban" in m:
        return "blocked"
    if "in_progress" in m or "in progress" in m:
        # Это не ошибка для AM — пропускаем репортинг, чтобы не ловить 422 по enum
        return None
    # Неизвестный тип — лучше не отправлять, чтобы избежать 422
    return None

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
        # Получаем данные аккаунта из выделения Account Manager (плоская структура)
        account_data = account_allocation
        account_id = account_data['account_id']
        
        logger.info(f"🔄 AccountManager: Отправка приглашения для цели {target.id} через аккаунт {account_id}")
        
        # Обновляем попытку отправки приглашения
        # Статус оставляем PENDING до фактического результата,
        # чтобы не использовать несуществующий enum IN_PROGRESS.
        target.attempt_count = (target.attempt_count or 0) + 1
        # В модели InviteTarget есть поле last_attempt_at вместо completed_at/in_progress
        if hasattr(target, "last_attempt_at"):
            target.last_attempt_at = datetime.utcnow()
        target.updated_at = datetime.utcnow()
        db.commit()
        
        # Подготавливаем данные цели для адаптера
        target_data = {}
        if target.username:
            target_data['username'] = target.username
        if target.phone_number:
            target_data['phone_number'] = target.phone_number
        if target.user_id_platform:
            target_data['user_id_platform'] = target.user_id_platform
            
        # Подготавливаем данные приглашения
        invite_data = {
            'group_id': task.settings.get('group_id') if task.settings else None,
            'message': task.settings.get('message') if task.settings else None
        }
        
        logger.info(f"🔍 AccountManager: Данные для приглашения - target: {target_data}, invite: {invite_data}")
        
        # ✅ КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Используем аккаунт из Account Manager вместо прямого вызова
        # Account Manager уже проверил лимиты, статус, блокировки
        # Формируем "облегченный" объект аккаунта для адаптера.
        # Добавляем owner_user_id, чтобы адаптер мог передать его в Integration Service.
        account_for_adapter = type('Account', (), {
            'account_id': account_id,
            'username': account_data.get('username'),
            'phone': account_data.get('phone'),
            'session_string': account_data.get('session_string'),
            'api_id': account_data.get('api_id'),
            'api_hash': account_data.get('api_hash'),
            'owner_user_id': task.user_id,
        })()
        
        # Выполняем приглашение через адаптер с аккаунтом от Account Manager
        result = await adapter.send_invite(account_for_adapter, target_data, invite_data)
        
        # Детальное логирование результата адаптера
        try:
            logger.info(
                "🔍 AccountManager: Результат отправки приглашения "
                f"target_id={target.id}, account_id={account_id}, "
                f"status={getattr(result, 'status', None)}, "
                f"is_success={getattr(result, 'is_success', None)}, "
                f"error_code={getattr(result, 'error_code', None)}, "
                f"error_message={getattr(result, 'error_message', None)}"
            )
        except Exception:
            # Никогда не ломаем основной поток из‑за логирования
            logger.warning("⚠️ AccountManager: Ошибка при логировании результата InviteResult", exc_info=True)
        
        # Обрабатываем результат
        if result.is_success:
            logger.info(f"✅ AccountManager: Успешное приглашение для цели {target.id} через аккаунт {account_id}")
            # В модели InviteTarget успешная отправка помечается как INVITED
            target.status = TargetStatus.INVITED
            # Используем invite_sent_at вместо несуществующего completed_at
            if hasattr(target, "invite_sent_at"):
                target.invite_sent_at = datetime.utcnow()
            target.error_message = None
            if hasattr(target, "error_code"):
                target.error_code = None
            if hasattr(target, "sent_from_account_id"):
                target.sent_from_account_id = account_id
        else:
            # Мягкие отказы (в т.ч. IN_PROGRESS из Integration Service) обрабатываем как ретрай, не помечая цель FAILED
            msg_lower = (result.error_message or "").lower()
            in_progress = (result.error_code == "in_progress") or ("in_progress" in msg_lower) or ("in progress" in msg_lower)
            if in_progress:
                logger.info(
                    "⏳ AccountManager: Детали in_progress для цели "
                    f"{target.id}: status={result.status}, error_code={result.error_code}, "
                    f"error_message={result.error_message}"
                )
            if result.status == InviteResultStatus.RATE_LIMITED and in_progress:
                logger.info(f"⏳ AccountManager: Операция в процессе для цели {target.id} (in_progress). Планируем повтор")
                target.status = TargetStatus.PENDING
                target.error_message = "in_progress"
                # Ничего не репортим в AM, чтобы не засорять статистику
            else:
                logger.warning(f"⚠️ AccountManager: Неудачное приглашение для цели {target.id}: {result.error_message}")
                target.status = TargetStatus.FAILED
                target.error_message = result.error_message
            
            # Уведомляем Account Manager об ошибке для корректировки лимитов/блокировок
            # Репортим в AM только если это не in_progress и тип известен
            if not (result.status == InviteResultStatus.RATE_LIMITED and in_progress):
                am_error_type = _map_error_type_for_am(result.error_message)
                if am_error_type:
                    await account_manager.handle_error(
                        account_id=account_id,
                        error_type=am_error_type,
                        error_message=str(result.error_message),
                        context={
                            'target_id': target.id,
                            'task_id': task.id,
                            'action': 'invite'
                        }
                    )
                else:
                    logger.info("ℹ️ Пропускаем handle_error в AM: неизвестный/некритичный тип ошибки для enum (во избежание 422)")
        
        target.updated_at = datetime.utcnow()
        
        # Пишем лог выполнения приглашения в invite_execution_logs
        try:
            action = ActionType.INVITE_SUCCESSFUL if result.is_success else ActionType.INVITE_FAILED
            level = LogLevel.INFO if result.is_success else LogLevel.WARNING
            status_str = (
                result.status.value if hasattr(result, "status") and hasattr(result.status, "value") else str(result.status)
            )
            log_entry = InviteExecutionLog(
                task_id=task.id,
                target_id=target.id,
                account_id=str(account_id),
                action_type=action,
                level=level,
                message=getattr(result, "message", None) or ("Invite successful" if result.is_success else "Invite failed"),
                execution_time_ms=int(result.execution_time * 1000) if getattr(result, "execution_time", None) else None,
                details={
                    "result_status": status_str,
                    "target_username": target.username,
                    "target_user_id": target.user_id_platform,
                    "target_phone": target.phone_number,
                    "error_code": getattr(result, "error_code", None),
                    "error_message": getattr(result, "error_message", None),
                    "platform_response": getattr(result, "platform_response", None),
                },
            )
            db.add(log_entry)
        except Exception:
            # Лог не должен ломать основную транзакцию
            logger.warning(
                "⚠️ AccountManager: не удалось записать InviteExecutionLog для цели %s",
                target.id,
                exc_info=True,
            )
        
        # Коммитим изменения с обработкой ошибок (цель + лог)
        try:
            db.commit()
        except Exception as db_error:
            logger.error(f"❌ Ошибка сохранения в БД для цели {target.id} и лога: {str(db_error)}")
            db.rollback()
            # Повторная попытка коммита
            try:
                target.updated_at = datetime.utcnow()
                db.add(log_entry)
                db.commit()
            except Exception as retry_error:
                logger.error(f"❌ Повторная ошибка сохранения в БД для цели {target.id}: {str(retry_error)}")
                db.rollback()
        
        # Возвращаем результат с временем выполнения
        result.execution_time = (datetime.utcnow() - start_time).total_seconds()
        result.account_id = account_id
        
        return result
        
    except Exception as e:
        e_str = str(e)
        logger.error(
            "❌ AccountManager: Исключение при отправке приглашения "
            f"для цели {target.id}: type={type(e).__name__}, message={e_str!r}",
            exc_info=True
        )
        
        # Обновляем цель как неудачную
        target.status = TargetStatus.FAILED
        target.error_message = e_str
        target.updated_at = datetime.utcnow()
        
        try:
            db.commit()
        except Exception as db_error:
            logger.error(f"❌ Ошибка сохранения ошибки в БД для цели {target.id}: {str(db_error)}")
            db.rollback()
        
        # Уведомляем Account Manager об ошибке
        if account_allocation:
            try:
                e_low = e_str.lower()
                am_error_type = _map_error_type_for_am(e_str) or ("blocked" if "blocked" in e_low else None)
                if am_error_type:
                    await account_manager.handle_error(
                        account_id=account_allocation['account_id'],
                        error_type=am_error_type,
                        error_message=e_str,
                        context={
                            'target_id': target.id,
                            'task_id': task.id,
                            'action': 'invite',
                            'error': 'exception_during_invite'
                        }
                    )
                else:
                    logger.info("ℹ️ Пропускаем handle_error в AM для exception: неизвестный тип (во избежание 422)")
            except Exception as error_report_error:
                logger.error(f"❌ Ошибка при уведомлении Account Manager об ошибке: {str(error_report_error)}")
        
        # Пишем лог об ошибке выполнения
        try:
            err_log = InviteExecutionLog(
                task_id=task.id,
                target_id=target.id,
                account_id=str(account_allocation.get("account_id")) if account_allocation else None,
                action_type=ActionType.ERROR_OCCURRED,
                level=LogLevel.ERROR,
                message=e_str,
                execution_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
                error_message=e_str,
            )
            db.add(err_log)
            db.commit()
        except Exception:
            logger.warning(
                "⚠️ AccountManager: не удалось записать InviteExecutionLog для исключения по цели %s",
                target.id,
                exc_info=True,
            )

        # Возвращаем результат с ошибкой
        return InviteResult(
            status=InviteResultStatus.FAILED,
            error_message=e_str,
            account_id=account_allocation['account_id'] if account_allocation else None,
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
