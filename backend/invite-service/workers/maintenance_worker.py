"""
Celery воркеры для периодических задач обслуживания
"""

import logging
from datetime import datetime, timedelta
from typing import List
from sqlalchemy import and_

from workers.celery_app import celery_app
from app.core.database import get_db_session
from app.models import InviteTask, InviteTarget, InviteExecutionLog, TaskStatus, TargetStatus

logger = logging.getLogger(__name__)


@celery_app.task
def cleanup_expired_tasks():
    """Очистка устаревших задач и связанных данных"""
    
    logger.info("Запуск очистки устаревших задач")
    
    with get_db_session() as db:
        try:
            # Определяем что считается устаревшим (30 дней)
            expiry_date = datetime.utcnow() - timedelta(days=30)
            
            # Находим устаревшие завершенные задачи
            expired_tasks = db.query(InviteTask).filter(
                and_(
                    InviteTask.status.in_([TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]),
                    InviteTask.updated_at < expiry_date
                )
            ).all()
            
            if not expired_tasks:
                logger.info("Устаревших задач для очистки не найдено")
                return "Нет устаревших задач"
            
            logger.info(f"Найдено {len(expired_tasks)} устаревших задач для очистки")
            
            cleaned_tasks = 0
            cleaned_targets = 0
            cleaned_logs = 0
            
            for task in expired_tasks:
                task_id = task.id
                
                # Удаляем логи выполнения (каскадно удалятся через FK)
                logs_count = db.query(InviteExecutionLog).filter(
                    InviteExecutionLog.task_id == task_id
                ).count()
                
                # Удаляем цели (каскадно удалятся через FK)
                targets_count = db.query(InviteTarget).filter(
                    InviteTarget.task_id == task_id
                ).count()
                
                # Удаляем саму задачу (каскадно удалятся связанные записи)
                db.delete(task)
                
                cleaned_tasks += 1
                cleaned_targets += targets_count
                cleaned_logs += logs_count
                
                logger.debug(f"Удалена задача {task_id}: {targets_count} целей, {logs_count} логов")
            
            db.commit()
            
            result = f"Очищено: {cleaned_tasks} задач, {cleaned_targets} целей, {cleaned_logs} логов"
            logger.info(result)
            return result
            
        except Exception as e:
            logger.error(f"Ошибка очистки устаревших задач: {str(e)}")
            db.rollback()
            raise


@celery_app.task
def update_rate_limits():
    """Обновление rate limits и статусов аккаунтов"""
    
    logger.debug("Обновление rate limits")
    
    # TODO: Интеграция с Redis для сброса почасовых лимитов
    # TODO: Проверка истечения flood wait ограничений
    # TODO: Обновление статусов аккаунтов в Integration Service
    
    return "Rate limits обновлены"


@celery_app.task
def calculate_task_progress():
    """Пересчет прогресса выполнения задач"""
    
    logger.info("Пересчет прогресса выполнения задач")
    
    with get_db_session() as db:
        try:
            # Находим активные задачи
            active_tasks = db.query(InviteTask).filter(
                InviteTask.status.in_([TaskStatus.RUNNING, TaskStatus.PAUSED])
            ).all()
            
            if not active_tasks:
                logger.debug("Активных задач для пересчета прогресса не найдено")
                return "Нет активных задач"
            
            updated_count = 0
            
            for task in active_tasks:
                # Подсчет целей по статусам
                total_targets = db.query(InviteTarget).filter(
                    InviteTarget.task_id == task.id
                ).count()
                
                completed_targets = db.query(InviteTarget).filter(
                    and_(
                        InviteTarget.task_id == task.id,
                        InviteTarget.status == TargetStatus.INVITED
                    )
                ).count()
                
                failed_targets = db.query(InviteTarget).filter(
                    and_(
                        InviteTarget.task_id == task.id,
                        InviteTarget.status == TargetStatus.FAILED
                    )
                ).count()
                
                # Обновление счетчиков если они изменились
                if (task.target_count != total_targets or 
                    task.completed_count != completed_targets or 
                    task.failed_count != failed_targets):
                    
                    task.target_count = total_targets
                    task.completed_count = completed_targets
                    task.failed_count = failed_targets
                    task.updated_at = datetime.utcnow()
                    
                    # Вычисление прогресса
                    if total_targets > 0:
                        task.progress_percentage = (completed_targets + failed_targets) * 100.0 / total_targets
                    else:
                        task.progress_percentage = 0.0
                    
                    updated_count += 1
                    
                    logger.debug(f"Обновлен прогресс задачи {task.id}: {task.progress_percentage:.1f}%")
            
            if updated_count > 0:
                db.commit()
                logger.info(f"Обновлен прогресс {updated_count} задач")
            
            return f"Обновлено {updated_count} задач"
            
        except Exception as e:
            logger.error(f"Ошибка пересчета прогресса задач: {str(e)}")
            db.rollback()
            raise


@celery_app.task
def cleanup_failed_targets():
    """Очистка целей с множественными неудачными попытками"""
    
    logger.info("Очистка целей с множественными неудачными попытками")
    
    with get_db_session() as db:
        try:
            # Находим цели с большим количеством неудачных попыток (>5)
            failed_targets = db.query(InviteTarget).filter(
                and_(
                    InviteTarget.status == TargetStatus.FAILED,
                    InviteTarget.attempt_count > 5,
                    InviteTarget.updated_at < datetime.utcnow() - timedelta(days=7)  # Старше 7 дней
                )
            ).all()
            
            if not failed_targets:
                logger.debug("Нет целей для очистки")
                return "Нет целей для очистки"
            
            cleaned_count = 0
            
            for target in failed_targets:
                # Удаляем связанные логи
                db.query(InviteExecutionLog).filter(
                    InviteExecutionLog.target_id == target.id
                ).delete()
                
                # Удаляем цель
                db.delete(target)
                cleaned_count += 1
            
            db.commit()
            
            result = f"Очищено {cleaned_count} неудачных целей"
            logger.info(result)
            return result
            
        except Exception as e:
            logger.error(f"Ошибка очистки неудачных целей: {str(e)}")
            db.rollback()
            raise


@celery_app.task
def health_check_services():
    """Проверка здоровья внешних сервисов"""
    
    logger.debug("Проверка здоровья внешних сервисов")
    
    results = {
        "integration_service": False,
        "redis": False,
        "database": False
    }
    
    # Проверка Integration Service
    try:
        from app.services.integration_client import get_integration_client
        
        client = get_integration_client()
        results["integration_service"] = await client.health_check()
        
    except Exception as e:
        logger.warning(f"Integration Service недоступен: {str(e)}")
    
    # Проверка Redis
    try:
        import redis
        r = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379/0'))
        r.ping()
        results["redis"] = True
        
    except Exception as e:
        logger.warning(f"Redis недоступен: {str(e)}")
    
    # Проверка Database
    try:
        with get_db_session() as db:
            db.execute("SELECT 1")
            results["database"] = True
            
    except Exception as e:
        logger.warning(f"Database недоступна: {str(e)}")
    
    # Логирование результатов
    healthy_count = sum(results.values())
    total_count = len(results)
    
    if healthy_count == total_count:
        logger.info("Все внешние сервисы доступны")
    else:
        unhealthy = [service for service, status in results.items() if not status]
        logger.warning(f"Недоступные сервисы: {unhealthy}")
    
    return f"Здоровых сервисов: {healthy_count}/{total_count}"


@celery_app.task
def generate_daily_report():
    """Генерация ежедневного отчета по выполненным задачам"""
    
    logger.info("Генерация ежедневного отчета")
    
    with get_db_session() as db:
        try:
            # Статистика за последние 24 часа
            yesterday = datetime.utcnow() - timedelta(days=1)
            
            # Количество задач
            completed_tasks = db.query(InviteTask).filter(
                and_(
                    InviteTask.status == TaskStatus.COMPLETED,
                    InviteTask.end_time >= yesterday
                )
            ).count()
            
            failed_tasks = db.query(InviteTask).filter(
                and_(
                    InviteTask.status == TaskStatus.FAILED,
                    InviteTask.end_time >= yesterday
                )
            ).count()
            
            # Количество приглашений
            total_invites = db.query(InviteTarget).filter(
                and_(
                    InviteTarget.status == TargetStatus.INVITED,
                    InviteTarget.invite_sent_at >= yesterday
                )
            ).count()
            
            failed_invites = db.query(InviteTarget).filter(
                and_(
                    InviteTarget.status == TargetStatus.FAILED,
                    InviteTarget.updated_at >= yesterday
                )
            ).count()
            
            report = {
                "date": datetime.utcnow().strftime("%Y-%m-%d"),
                "completed_tasks": completed_tasks,
                "failed_tasks": failed_tasks,
                "total_invites": total_invites,
                "failed_invites": failed_invites,
                "success_rate": (total_invites / (total_invites + failed_invites) * 100) if (total_invites + failed_invites) > 0 else 0
            }
            
            logger.info(f"Ежедневный отчет: {report}")
            
            # TODO: Отправка отчета по email или в Slack
            # TODO: Сохранение отчета в файл или базу данных
            
            return f"Отчет сгенерирован: {completed_tasks} задач завершено, {total_invites} приглашений отправлено"
            
        except Exception as e:
            logger.error(f"Ошибка генерации ежедневного отчета: {str(e)}")
            raise 