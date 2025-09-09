"""
Celery воркеры для выполнения задач приглашений
"""

import asyncio
import logging
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from celery import current_task
from celery.exceptions import Retry, WorkerLostError
from sqlalchemy.orm import Session

from workers.celery_app import celery_app
from app.core.database import get_db_session
from app.models import InviteTask, InviteTarget, InviteExecutionLog, TaskStatus, TargetStatus
from app.adapters.factory import get_platform_adapter
from app.adapters.base import InviteResult, InviteResultStatus

logger = logging.getLogger(__name__)


def _filter_admin_accounts(accounts, task: InviteTask):
    """Фильтрация аккаунтов с проверкой администраторских прав
    
    Применяет ту же логику, что и в /check-admin-rights endpoint
    для выбора только администраторов с правами приглашать пользователей
    """
    if not accounts:
        return []
    
    admin_accounts = []
    
    # Получаем group_id из настроек задачи
    group_id = None
    if hasattr(task, 'settings') and task.settings:
        group_id = task.settings.get('group_id')
    
    if not group_id:
        logger.warning(f"Задача {task.id} не содержит group_id в настройках, используем базовую фильтрацию")
        # Если нет group_id, используем старую логику (только базовые проверки)
        return _filter_accounts_basic(accounts)
    
    logger.info(f"Проверяем админские права для группы {group_id} для {len(accounts)} аккаунтов")
    
    for account in accounts:
        # Базовая проверка активности аккаунта
        if not hasattr(account, 'status') or account.status != 'active':
            logger.debug(f"Аккаунт {account.account_id} не активен: {getattr(account, 'status', 'unknown')}")
            continue
            
        # Проверяем лимиты
        daily_used = getattr(account, 'daily_used', 0)
        daily_limit = getattr(account, 'daily_limit', 50)
        
        if daily_used >= daily_limit:
            logger.warning(f"Аккаунт {account.account_id} достиг дневного лимита: {daily_used}/{daily_limit}")
            continue
            
        # Проверяем флуд ограничения
        if hasattr(account, 'flood_wait_until') and account.flood_wait_until:
            if account.flood_wait_until > datetime.utcnow():
                logger.warning(f"Аккаунт {account.account_id} в флуд ожидании до {account.flood_wait_until}")
                continue
        
        # РЕАЛЬНАЯ ПРОВЕРКА АДМИНСКИХ ПРАВ
        try:
            is_admin = _check_account_admin_rights(account.account_id, group_id)
            if is_admin:
                logger.info(f"✅ Аккаунт {account.account_id} является администратором группы {group_id} с правами приглашать")
                admin_accounts.append(account)
            else:
                logger.warning(f"❌ Аккаунт {account.account_id} НЕ является администратором группы {group_id} или не имеет прав приглашать")
        except Exception as e:
            logger.error(f"Ошибка проверки админских прав для аккаунта {account.account_id}: {str(e)}")
            # В случае ошибки API не добавляем аккаунт в админские
            continue
    
    logger.info(f"Фильтрация аккаунтов: из {len(accounts)} доступно {len(admin_accounts)} админских аккаунтов")
    return admin_accounts


async def _filter_admin_accounts_async(accounts, task: InviteTask):
    """Асинхронная фильтрация аккаунтов с проверкой администраторских прав
    
    Применяет ту же логику, что и в /check-admin-rights endpoint
    для выбора только администраторов с правами приглашать пользователей
    """
    if not accounts:
        return []
    
    admin_accounts = []
    
    # Получаем group_id из настроек задачи
    group_id = None
    if hasattr(task, 'settings') and task.settings:
        group_id = task.settings.get('group_id')
    
    if not group_id:
        logger.warning(f"Задача {task.id} не содержит group_id в настройках, используем базовую фильтрацию")
        # Если нет group_id, используем старую логику (только базовые проверки)
        return _filter_accounts_basic(accounts)
    
    logger.info(f"Проверяем админские права для группы {group_id} для {len(accounts)} аккаунтов")
    
    for account in accounts:
        # Базовая проверка активности аккаунта
        if not hasattr(account, 'status') or account.status != 'active':
            logger.debug(f"Аккаунт {account.account_id} не активен: {getattr(account, 'status', 'unknown')}")
            continue
            
        # Проверяем лимиты
        daily_used = getattr(account, 'daily_used', 0)
        daily_limit = getattr(account, 'daily_limit', 50)
        
        if daily_used >= daily_limit:
            logger.warning(f"Аккаунт {account.account_id} достиг дневного лимита: {daily_used}/{daily_limit}")
            continue
            
        # Проверяем флуд ограничения
        if hasattr(account, 'flood_wait_until') and account.flood_wait_until:
            if account.flood_wait_until > datetime.utcnow():
                logger.warning(f"Аккаунт {account.account_id} в флуд ожидании до {account.flood_wait_until}")
                continue
        
        # РЕАЛЬНАЯ ПРОВЕРКА АДМИНСКИХ ПРАВ
        try:
            is_admin = await _check_account_admin_rights_async(account.account_id, group_id)
            if is_admin:
                logger.info(f"✅ Аккаунт {account.account_id} является администратором группы {group_id} с правами приглашать")
                admin_accounts.append(account)
            else:
                logger.warning(f"❌ Аккаунт {account.account_id} НЕ является администратором группы {group_id} или не имеет прав приглашать")
        except Exception as e:
            logger.error(f"Ошибка проверки админских прав для аккаунта {account.account_id}: {str(e)}")
            # В случае ошибки API не добавляем аккаунт в админские
            continue
    
    logger.info(f"Фильтрация аккаунтов: из {len(accounts)} доступно {len(admin_accounts)} админских аккаунтов")
    return admin_accounts


def _filter_accounts_basic(accounts):
    """Базовая фильтрация аккаунтов без проверки админских прав (fallback)"""
    active_accounts = []
    
    for account in accounts:
        # Базовая проверка активности аккаунта
        if not hasattr(account, 'status') or account.status != 'active':
            continue
            
        # Проверяем лимиты
        daily_used = getattr(account, 'daily_used', 0)
        daily_limit = getattr(account, 'daily_limit', 50)
        
        if daily_used >= daily_limit:
            logger.warning(f"Аккаунт {account.account_id} достиг дневного лимита: {daily_used}/{daily_limit}")
            continue
            
        # Проверяем флуд ограничения
        if hasattr(account, 'flood_wait_until') and account.flood_wait_until:
            if account.flood_wait_until > datetime.utcnow():
                logger.warning(f"Аккаунт {account.account_id} в флуд ожидании до {account.flood_wait_until}")
                continue
        
        logger.info(f"Аккаунт {account.account_id} прошел базовые проверки (активен, лимиты OK) - admin права не проверялись")
        active_accounts.append(account)
    
    return active_accounts


async def _check_account_admin_rights_async(account_id: str, group_id: str) -> bool:
    """Асинхронная проверка административных прав аккаунта в группе/канале
    
    Возвращает True если аккаунт является администратором с правами приглашать пользователей
    """
    try:
        # Используем аутентифицированный клиент Integration Service
        from app.services.integration_client import IntegrationServiceClient
        
        integration_client = IntegrationServiceClient()
        
        response = await integration_client._make_request(
            method="POST",
            endpoint=f"/api/v1/telegram/accounts/{account_id}/check-admin",
            json_data={
                "group_id": group_id,
                "required_permissions": ["invite_users"]
            }
        )
        
        is_admin = response.get('is_admin', False)
        has_invite_permission = 'invite_users' in response.get('permissions', [])
        
        logger.debug(f"Проверка админ прав для {account_id}: is_admin={is_admin}, permissions={response.get('permissions', [])}")
        return is_admin and has_invite_permission
        
    except Exception as e:
        logger.error(f"Ошибка при проверке админ прав для {account_id}: {str(e)}")
        return False


def _check_account_admin_rights(account_id: str, group_id: str) -> bool:
    """Синхронная обертка для проверки административных прав
    
    Возвращает True если аккаунт является администратором с правами приглашать пользователей
    """
    try:
        # Создаем новый event loop если его нет
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Выполняем асинхронную проверку
        return loop.run_until_complete(_check_account_admin_rights_async(account_id, group_id))
        
    except Exception as e:
        logger.error(f"Ошибка в синхронной обертке проверки админ прав для {account_id}: {str(e)}")
        return False


@celery_app.task(bind=True, max_retries=3)
def execute_invite_task(self, task_id: int):
    """
    Главная задача выполнения приглашений
    
    Args:
        task_id: ID задачи приглашений
    """
    logger.info(f"🚀 CELERY WORKER: Получена задача выполнения приглашений: {task_id}")
    logger.info(f"🚀 CELERY WORKER: Celery task ID: {self.request.id}")
    
    try:
        with get_db_session() as db:
            # Получение задачи
            task = db.query(InviteTask).filter(InviteTask.id == task_id).first()
            
            if not task:
                logger.error(f"❌ CELERY WORKER: Задача {task_id} не найдена")
                raise Exception(f"Задача {task_id} не найдена")
            
            logger.info(f"✅ CELERY WORKER: Задача {task_id} найдена, статус: {task.status}")
            
            if task.status not in [TaskStatus.PENDING, TaskStatus.PAUSED, TaskStatus.FAILED, TaskStatus.IN_PROGRESS]:
                logger.warning(f"⚠️ CELERY WORKER: Задача {task_id} имеет некорректный статус для выполнения: {task.status}")
                return f"Задача {task_id} не может быть выполнена со статусом {task.status}"
            
            # Обновление статуса на IN_PROGRESS (строковое значение enum)
            task.status = TaskStatus.IN_PROGRESS.value
            task.start_time = datetime.utcnow()
            task.updated_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Задача {task_id} переведена в статус RUNNING")
            
            # Получение Platform Adapter
            try:
                adapter = get_platform_adapter(task.platform)
            except ValueError as e:
                task.status = TaskStatus.FAILED
                task.error_message = f"Неподдерживаемая платформа: {str(e)}"
                task.end_time = datetime.utcnow()
                db.commit()
                raise
            
            # Асинхронное выполнение задачи
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = loop.run_until_complete(_execute_task_async(task, adapter, db))
                return result
            finally:
                loop.close()
                
    except Exception as e:
        logger.error(f"Ошибка выполнения задачи {task_id}: {str(e)}")
        
        # Обновление статуса на FAILED
        with get_db_session() as db:
            task = db.query(InviteTask).filter(InviteTask.id == task_id).first()
            if task:
                task.status = TaskStatus.FAILED.value
                task.error_message = str(e)
                task.end_time = datetime.utcnow()
                task.updated_at = datetime.utcnow()
                db.commit()
        
        # Retry если это временная ошибка
        if self.request.retries < self.max_retries and _is_retryable_error(e):
            countdown = 2 ** self.request.retries * 60  # Экспоненциальная задержка
            logger.info(f"Retry задачи {task_id} через {countdown} секунд")
            raise self.retry(countdown=countdown, exc=e)
        
        raise


async def _execute_task_async(task: InviteTask, adapter, db: Session) -> str:
    """Асинхронное выполнение задачи приглашений"""
    
    try:
        # Инициализация аккаунтов
        logger.info(f"Инициализация аккаунтов для задачи {task.id}")
        all_accounts = await adapter.initialize_accounts(task.user_id)
        
        if not all_accounts:
            raise Exception("Нет доступных аккаунтов для выполнения задачи")
        
        logger.info(f"Найдено {len(all_accounts)} аккаунтов, применяем фильтрацию по админским правам")
        
        # Фильтрация аккаунтов с проверкой админских прав  
        accounts = await _filter_admin_accounts_async(all_accounts, task)
        
        if not accounts:
            raise Exception(f"Нет доступных аккаунтов с административными правами. Из {len(all_accounts)} аккаунтов ни один не прошел проверку на админские права и лимиты")
        
        logger.info(f"Найдено {len(accounts)} активных аккаунтов для задачи {task.id}")
        
        # Получение целевой аудитории
        targets = db.query(InviteTarget).filter(
            InviteTarget.task_id == task.id,
            InviteTarget.status == TargetStatus.PENDING
        ).all()
        
        if not targets:
            logger.warning(f"Нет целей для обработки в задаче {task.id}")
            task.status = TaskStatus.COMPLETED.value
            task.end_time = datetime.utcnow()
            db.commit()
            return f"Задача {task.id} завершена: нет целей для обработки"
        
        logger.info(f"Найдено {len(targets)} целей для обработки в задаче {task.id}")
        
        # Разбивка на батчи
        batch_size = task.settings.get('batch_size', 10) if task.settings else 10
        delay_between_batches = task.settings.get('delay_between_batches', 30) if task.settings else 30
        
        total_batches = (len(targets) + batch_size - 1) // batch_size
        logger.info(f"Разбиваем цели на {total_batches} батчей по {batch_size} элементов")
        
        # Запуск обработки по батчам
        for i in range(0, len(targets), batch_size):
            batch = targets[i:i + batch_size]
            batch_number = i // batch_size + 1
            
            logger.info(f"Запуск обработки батча {batch_number}/{total_batches} (размер: {len(batch)})")
            
            # Запуск задачи для батча
            process_target_batch.delay(
                task_id=task.id,
                target_ids=[t.id for t in batch],
                batch_number=batch_number
            )
            
            # Задержка между батчами (кроме последнего)
            if i + batch_size < len(targets):
                logger.debug(f"Ожидание {delay_between_batches}s между батчами")
                await asyncio.sleep(delay_between_batches)
        
        # Задача запущена, батчи обрабатываются асинхронно
        logger.info(f"Все батчи для задачи {task.id} запущены в обработку")
        return f"Задача {task.id} запущена: {total_batches} батчей отправлены в обработку"
        
    except Exception as e:
        logger.error(f"Ошибка в _execute_task_async для задачи {task.id}: {str(e)}")
        raise


@celery_app.task(bind=True, max_retries=5)
def process_target_batch(self, task_id: int, target_ids: List[int], batch_number: int = 1):
    """
    Обработка пакета целевых контактов
    
    Args:
        task_id: ID задачи
        target_ids: Список ID целей для обработки
        batch_number: Номер батча для логирования
    """
    logger.info(f"Обработка батча {batch_number} для задачи {task_id}: {len(target_ids)} целей")
    
    with get_db_session() as db:
        # Получение задачи и целей
        task = db.query(InviteTask).filter(InviteTask.id == task_id).first()
        if not task:
            logger.error(f"Задача {task_id} не найдена")
            return
        
        targets = db.query(InviteTarget).filter(InviteTarget.id.in_(target_ids)).all()
        if not targets:
            logger.warning(f"Цели для батча {batch_number} задачи {task_id} не найдены")
            return
        
        try:
            # Получение adapter
            adapter = get_platform_adapter(task.platform)
            
            # Асинхронная обработка батча
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = loop.run_until_complete(
                    _process_batch_async(task, targets, adapter, db, batch_number)
                )
                
                # Проверка завершения всей задачи
                _check_task_completion(task, db)
                
                return result
                
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Ошибка обработки батча {batch_number} задачи {task_id}: {str(e)}")
            
            # Retry если возможно
            if self.request.retries < self.max_retries and _is_retryable_error(e):
                countdown = 2 ** self.request.retries * 60
                logger.info(f"Retry батча {batch_number} задачи {task_id} через {countdown} секунд")
                raise self.retry(countdown=countdown, exc=e)
            
            # Если retry не помогает, отмечаем цели как failed
            for target in targets:
                if target.status == TargetStatus.PENDING:
                    target.status = TargetStatus.FAILED
                    target.error_message = f"Ошибка обработки батча: {str(e)}"
                    target.attempt_count += 1
                    target.updated_at = datetime.utcnow()
            
            db.commit()
            raise


async def _process_batch_async(
    task: InviteTask,
    targets: List[InviteTarget],
    adapter,
    db: Session,
    batch_number: int
) -> str:
    """Асинхронная обработка батча целей"""
    
    try:
        # Инициализация аккаунтов с фильтрацией по админским правам
        all_accounts = await adapter.initialize_accounts(task.user_id)
        if not all_accounts:
            raise Exception("Нет доступных аккаунтов")
            
        # Применяем фильтрацию по админским правам  
        accounts = await _filter_admin_accounts_async(all_accounts, task)
        if not accounts:
            raise Exception(f"Ни один аккаунт не прошел проверку на админские права. Из {len(all_accounts)} аккаунтов ни один не является администратором с правами приглашать пользователей")
        
        # Round-robin распределение по аккаунтам
        account_index = 0
        processed_count = 0
        success_count = 0
        failed_count = 0
        
        for target in targets:
            # Проверка статуса задачи (может быть отменена)
            db.refresh(task)
            if task.status in [TaskStatus.CANCELLED, TaskStatus.FAILED]:
                logger.info(f"Задача {task.id} отменена/провалена, прерываем обработку батча {batch_number}")
                break
            
            // 🔍 ДИАГНОСТИКА: Проверяем данные цели перед обработкой
            logger.info(f"🔍 DIAGNOSTIC: Подготовка к обработке цели {target.id}")
            logger.info(f"🔍 DIAGNOSTIC:   username: {repr(target.username)}")
            logger.info(f"🔍 DIAGNOSTIC:   phone_number: {repr(target.phone_number)}")
            logger.info(f"🔍 DIAGNOSTIC:   user_id_platform: {repr(target.user_id_platform)}")
            logger.info(f"🔍 DIAGNOSTIC:   has_any_identifier: {any([target.username, target.phone_number, target.user_id_platform])}")
            
            // ✅ ДОБАВЛЕНО: Пропускаем цели без идентификаторов
            if not any([target.username, target.phone_number, target.user_id_platform]):
                logger.warning(f"⚠️ Цель {target.id} не содержит идентификаторов, пропускаем")
                target.status = TargetStatus.FAILED
                target.error_message = "Цель не содержит идентификаторов для приглашения"
                target.attempt_count += 1
                target.updated_at = datetime.utcnow()
                db.commit()
                continue
            
            account = accounts[account_index % len(accounts)]
            
            try:
                # Выполнение приглашения
                result = await _send_single_invite(task, target, account, adapter, db)
                
                if result.is_success:
                    success_count += 1
                    task.completed_count += 1
                else:
                    failed_count += 1
                    task.failed_count += 1
                
                processed_count += 1
                
                # Переключение аккаунта
                account_index += 1
                
                # Задержка между приглашениями
                if processed_count < len(targets):
                    delay = task.delay_between_invites or 60
                    await asyncio.sleep(delay)
                
            except Exception as e:
                logger.error(f"Ошибка обработки цели {target.id}: {str(e)}")
                failed_count += 1
                task.failed_count += 1
                
                # Обновление цели
                target.status = TargetStatus.FAILED
                target.error_message = str(e)
                target.attempt_count += 1
                target.updated_at = datetime.utcnow()
        
        # Обновление статистики задачи
        task.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(
            f"Батч {batch_number} задачи {task.id} завершен: "
            f"обработано {processed_count}, успешно {success_count}, ошибок {failed_count}"
        )
        
        return f"Батч {batch_number}: {processed_count} обработано, {success_count} успешно"
        
    except Exception as e:
        logger.error(f"Ошибка в _process_batch_async батч {batch_number} задачи {task.id}: {str(e)}")
        raise


async def _send_single_invite(
    task: InviteTask,
    target: InviteTarget,
    account,
    adapter,
    db: Session
) -> InviteResult:
    """Отправка одного приглашения"""
    
    start_time = datetime.utcnow()
    
    try:
        // ✅ ДОБАВЛЕНО: Проверка наличия идентификаторов у цели перед обработкой
        if not any([target.username, target.phone_number, target.user_id_platform]):
            error_msg = f"Цель {target.id} не содержит идентификатора для приглашения (пропущена)"
            logger.warning(f"⚠️ {error_msg}")
            # Возвращаем результат с ошибкой вместо выбрасывания исключения
            return InviteResult(
                status=InviteResultStatus.FAILED,
                error_message=error_msg,
                account_id=account.account_id if account else None,
                execution_time=(datetime.utcnow() - start_time).total_seconds(),
                can_retry=False
            )
        
        # Подготовка данных цели
        target_data = {
            "username": target.username,
            "phone_number": target.phone_number,
            "user_id_platform": target.user_id_platform,
            "email": target.email
        }
        
        # 🔍 ДИАГНОСТИКА: подробное логирование данных цели из базы
        logger.info(f"🔍 DIAGNOSTIC: Подробные данные цели {target.id} из базы данных:")
        logger.info(f"🔍 DIAGNOSTIC:   username: {repr(target.username)} (type: {type(target.username)})")
        logger.info(f"🔍 DIAGNOSTIC:   phone_number: {repr(target.phone_number)} (type: {type(target.phone_number)})")
        logger.info(f"🔍 DIAGNOSTIC:   user_id_platform: {repr(target.user_id_platform)} (type: {type(target.user_id_platform)})")
        logger.info(f"🔍 DIAGNOSTIC:   email: {repr(target.email)} (type: {type(target.email)})")
        logger.info(f"🔍 DIAGNOSTIC:   any identifiers: {any([target.username, target.phone_number, target.user_id_platform])}")
        
        # Проверяем, что цель имеет хотя бы один идентификатор
        if not any([target.username, target.phone_number, target.user_id_platform]):
            error_msg = f"Цель {target.id} не содержит идентификатора для приглашения"
            logger.error(f"❌ {error_msg}")
            # Возвращаем результат с ошибкой вместо выбрасывания исключения
            return InviteResult(
                status=InviteResultStatus.FAILED,
                error_message=error_msg,
                account_id=account.account_id if account else None,
                execution_time=(datetime.utcnow() - start_time).total_seconds(),
                can_retry=False
            )
        
        # Подготовка данных приглашения
        invite_data = {
            "invite_type": task.settings.get('invite_type', 'group_invite') if task.settings else 'group_invite',
            "group_id": task.settings.get('group_id') if task.settings else None,
            "message": task.invite_message,
            "parse_mode": "text"
        }
        
        # Логируем данные приглашения для диагностики
        logger.info(f"🔍 DIAGNOSTIC: Данные приглашения: invite_type={invite_data['invite_type']}, group_id={invite_data['group_id']}")
        
        # Валидация цели
        is_valid = await adapter.validate_target(target_data)
        logger.info(f"🔍 DIAGNOSTIC: Результат валидации цели {target.id}: {is_valid}")
        
        if not is_valid:
            error_msg = "Некорректные данные цели - отсутствуют необходимые идентификаторы"
            logger.error(f"❌ {error_msg} для цели {target.id}")
            # Возвращаем результат с ошибкой вместо выбрасывания исключения
            return InviteResult(
                status=InviteResultStatus.FAILED,
                error_message=error_msg,
                account_id=account.account_id if account else None,
                execution_time=(datetime.utcnow() - start_time).total_seconds(),
                can_retry=False
            )
        
        # Отправка приглашения
        result = await adapter.send_invite(account, target_data, invite_data)
        
        # Обновление цели
        target.status = TargetStatus.INVITED if result.is_success else TargetStatus.FAILED
        target.invite_sent_at = result.sent_at
        target.error_message = result.error_message
        target.error_code = result.error_code
        target.sent_from_account_id = account.account_id
        target.attempt_count += 1
        target.updated_at = datetime.utcnow()
        
        # Логирование выполнения
        from app.models.invite_execution_log import ActionType, LogLevel
        
        log_entry = InviteExecutionLog(
            task_id=task.id,
            target_id=target.id,
            account_id=account.account_id,
            action_type=ActionType.INVITE_SENT,
            level=LogLevel.INFO,
            message=result.message or "Invitation sent",
            execution_time_ms=int(result.execution_time * 1000) if result.execution_time else None,
            details={
                "platform_response": result.platform_response,
                "result_status": result.status.value if hasattr(result.status, 'value') else str(result.status)
            }
        )
        db.add(log_entry)
        
        db.commit()
        
        logger.debug(f"Приглашение для цели {target.id} выполнено: {result.status}")
        return result
        
    except Exception as e:
        # Обновление цели при ошибке
        target.status = TargetStatus.FAILED
        target.error_message = str(e)
        target.attempt_count += 1
        target.updated_at = datetime.utcnow()
        
        # Логирование ошибки
        from app.models.invite_execution_log import ActionType, LogLevel
        
        log_entry = InviteExecutionLog(
            task_id=task.id,
            target_id=target.id,
            account_id=account.account_id if account else None,
            action_type=ActionType.INVITE_FAILED,
            level=LogLevel.ERROR,
            message=str(e),
            execution_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
            error_message=str(e)
        )
        db.add(log_entry)
        
        db.commit()
        
        logger.error(f"Ошибка отправки приглашения для цели {target.id}: {str(e)}")
        raise


def _check_task_completion(task: InviteTask, db: Session):
    """Проверка завершения задачи"""
    
    # Подсчет оставшихся целей
    pending_count = db.query(InviteTarget).filter(
        InviteTarget.task_id == task.id,
        InviteTarget.status == TargetStatus.PENDING
    ).count()
    
    if pending_count == 0:
        # Все цели обработаны
        task.status = TaskStatus.COMPLETED
        task.end_time = datetime.utcnow()
        task.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Задача {task.id} полностью завершена")


def _is_retryable_error(error: Exception) -> bool:
    """Проверка возможности retry для ошибки"""
    
    # Не ретраим WorkerLostError и подобные
    if isinstance(error, WorkerLostError):
        return False
    
    # Ретраим network ошибки и временные проблемы
    error_str = str(error).lower()
    retryable_patterns = [
        'timeout',
        'connection',
        'network',
        'temporary',
        'rate limit',
        'flood wait'
    ]
    
    return any(pattern in error_str for pattern in retryable_patterns)


@celery_app.task(bind=True)
def single_invite_operation(self, task_id: int, target_id: int, account_id: int = None):
    """
    Отправка одиночного приглашения (для тестирования или ручного управления)
    
    Args:
        task_id: ID задачи
        target_id: ID цели
        account_id: ID аккаунта (опционально)
    """
    logger.info(f"Отправка одиночного приглашения: задача {task_id}, цель {target_id}")
    
    with get_db_session() as db:
        task = db.query(InviteTask).filter(InviteTask.id == task_id).first()
        target = db.query(InviteTarget).filter(InviteTarget.id == target_id).first()
        
        if not task or not target:
            logger.error(f"Задача {task_id} или цель {target_id} не найдены")
            return "Задача или цель не найдены"
        
        try:
            adapter = get_platform_adapter(task.platform)
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                all_accounts = loop.run_until_complete(adapter.initialize_accounts(task.user_id))
                if not all_accounts:
                    raise Exception("Нет доступных аккаунтов")
                
                # Применяем фильтрацию по админским правам
                accounts = _filter_admin_accounts(all_accounts, task)
                if not accounts:
                    raise Exception(f"Ни один аккаунт не прошел проверку на админские права. Из {len(all_accounts)} аккаунтов ни один не является администратором")
                
                # Выбор аккаунта
                account = None
                if account_id:
                    account = next((acc for acc in accounts if acc.account_id == account_id), None)
                
                if not account:
                    account = accounts[0]  // Первый доступный
                
                # Отправка приглашения
                result = loop.run_until_complete(_send_single_invite(task, target, account, adapter, db))
                
                return f"Приглашение отправлено: {result.status}"
                
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Ошибка одиночного приглашения: {str(e)}")
            return f"Ошибка: {str(e)}" 