#!/usr/bin/env python3
"""
Скрипт для очистки пустых целей приглашений в Telegram
"""

import sys
import os
import logging
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Добавляем путь к backend
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend', 'invite-service'))

from app.models import InviteTarget, InviteTask
from app.models.invite_target import TargetStatus

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def cleanup_empty_targets(task_id=None, dry_run=True):
    """Очистка пустых целей приглашений"""
    
    # Подключение к базе данных
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://user:password@localhost/invite_db')
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    db = SessionLocal()
    
    try:
        if task_id:
            # Очистка для конкретной задачи
            task = db.query(InviteTask).filter(InviteTask.id == task_id).first()
            if not task:
                logger.error(f"Задача {task_id} не найдена")
                return
            
            logger.info(f"Очистка задачи {task_id}: {task.name}")
            
            empty_targets = db.query(InviteTarget).filter(
                InviteTarget.task_id == task_id,
                InviteTarget.username.is_(None),
                InviteTarget.phone_number.is_(None),
                InviteTarget.user_id_platform.is_(None)
            ).all()
        else:
            # Очистка всех задач
            empty_targets = db.query(InviteTarget).filter(
                InviteTarget.username.is_(None),
                InviteTarget.phone_number.is_(None),
                InviteTarget.user_id_platform.is_(None)
            ).all()
        
        count = len(empty_targets)
        logger.info(f"Найдено пустых целей для очистки: {count}")
        
        if count == 0:
            logger.info("Нет пустых целей для очистки")
            return
        
        if dry_run:
            logger.info("РЕЖИМ ПРОСМОТРА - цели не будут удалены")
            for i, target in enumerate(empty_targets[:10]):  # Показываем первые 10
                logger.info(f"Пустая цель {i+1}: ID={target.id}, task_id={target.task_id}, full_name={target.full_name}")
        else:
            logger.info("Выполняется удаление пустых целей...")
            for target in empty_targets:
                db.delete(target)
            
            db.commit()
            logger.info(f"Удалено {count} пустых целей")
            
            # Обновляем счетчики в задачах
            if task_id:
                task = db.query(InviteTask).filter(InviteTask.id == task_id).first()
                if task:
                    new_count = db.query(InviteTarget).filter(InviteTarget.task_id == task_id).count()
                    task.target_count = new_count
                    task.updated_at = datetime.utcnow()
                    db.commit()
                    logger.info(f"Обновлен счетчик задачи {task_id}: {new_count}")
            else:
                # Обновляем счетчики для всех задач
                tasks = db.query(InviteTask).all()
                for task in tasks:
                    new_count = db.query(InviteTarget).filter(InviteTarget.task_id == task.id).count()
                    if task.target_count != new_count:
                        task.target_count = new_count
                        task.updated_at = datetime.utcnow()
                        logger.info(f"Обновлен счетчик задачи {task.id}: {new_count}")
                
                db.commit()
            
        return count
        
    finally:
        db.close()

if __name__ == "__main__":
    task_id = None
    dry_run = True
    
    for arg in sys.argv[1:]:
        if arg == "--execute":
            dry_run = False
        else:
            try:
                task_id = int(arg)
            except ValueError:
                logger.error("Неверный формат аргументов")
                logger.info("Использование: python cleanup_empty_targets.py [--execute] [task_id]")
                sys.exit(1)
    
    if dry_run:
        logger.info("Запущен в режиме просмотра (dry-run)")
    else:
        logger.info("Запущен в режиме выполнения (execute)")
        logger.warning("БУДЬТЕ ОСТОРОЖНЫ! Будут удалены реальные данные!")
    
    cleanup_empty_targets(task_id, dry_run)