#!/usr/bin/env python3
"""
Скрипт для диагностики целей приглашений в Telegram
"""

import sys
import os
import logging
from sqlalchemy import create_engine, text
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

def diagnose_invite_targets(task_id=None):
    """Диагностика целей приглашений"""
    
    # Подключение к базе данных
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://user:password@localhost/invite_db')
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    db = SessionLocal()
    
    try:
        if task_id:
            # Анализ конкретной задачи
            task = db.query(InviteTask).filter(InviteTask.id == task_id).first()
            if not task:
                logger.error(f"Задача {task_id} не найдена")
                return
            
            logger.info(f"Анализ задачи {task_id}: {task.name}")
            logger.info(f"Всего целей в задаче: {task.target_count}")
            
            targets = db.query(InviteTarget).filter(InviteTarget.task_id == task_id).all()
        else:
            # Анализ всех задач
            targets = db.query(InviteTarget).all()
        
        total_targets = len(targets)
        logger.info(f"Всего целей для анализа: {total_targets}")
        
        # Статистика по идентификаторам
        has_username = 0
        has_phone = 0
        has_user_id = 0
        has_any_identifier = 0
        empty_targets = 0
        
        status_stats = {}
        
        for target in targets:
            # Подсчет статистики по идентификаторам
            if target.username:
                has_username += 1
            
            if target.phone_number:
                has_phone += 1
                
            if target.user_id_platform:
                has_user_id += 1
            
            if target.username or target.phone_number or target.user_id_platform:
                has_any_identifier += 1
            else:
                empty_targets += 1
            
            # Подсчет статистики по статусам
            status = target.status
            if status not in status_stats:
                status_stats[status] = 0
            status_stats[status] += 1
        
        logger.info("=== СТАТИСТИКА ПО ИДЕНТИФИКАТОРАМ ===")
        logger.info(f"Целей с username: {has_username} ({has_username/total_targets*100:.2f}%)")
        logger.info(f"Целей с phone_number: {has_phone} ({has_phone/total_targets*100:.2f}%)")
        logger.info(f"Целей с user_id_platform: {has_user_id} ({has_user_id/total_targets*100:.2f}%)")
        logger.info(f"Целей с любыми идентификаторами: {has_any_identifier} ({has_any_identifier/total_targets*100:.2f}%)")
        logger.info(f"ПУСТЫХ целей (без идентификаторов): {empty_targets} ({empty_targets/total_targets*100:.2f}%)")
        
        logger.info("=== СТАТИСТИКА ПО СТАТУСАМ ===")
        for status, count in status_stats.items():
            logger.info(f"Статус {status}: {count} ({count/total_targets*100:.2f}%)")
        
        # Примеры пустых целей
        if empty_targets > 0:
            logger.info("=== ПРИМЕРЫ ПУСТЫХ ЦЕЛЕЙ ===")
            empty_targets_list = [t for t in targets if not (t.username or t.phone_number or t.user_id_platform)][:10]
            for i, target in enumerate(empty_targets_list):
                logger.info(f"Пустая цель {i+1}: ID={target.id}, task_id={target.task_id}, full_name={target.full_name}")
                logger.info(f"  Данные: username={target.username}, phone={target.phone_number}, user_id={target.user_id_platform}")
                logger.info(f"  Источник: {target.source}")
                if target.extra_data:
                    logger.info(f"  Доп. данные: {target.extra_data}")
        
        return {
            'total_targets': total_targets,
            'has_username': has_username,
            'has_phone': has_phone,
            'has_user_id': has_user_id,
            'has_any_identifier': has_any_identifier,
            'empty_targets': empty_targets,
            'status_stats': status_stats
        }
        
    finally:
        db.close()

if __name__ == "__main__":
    task_id = None
    if len(sys.argv) > 1:
        try:
            task_id = int(sys.argv[1])
        except ValueError:
            logger.error("Неверный формат ID задачи")
            sys.exit(1)
    
    diagnose_invite_targets(task_id)