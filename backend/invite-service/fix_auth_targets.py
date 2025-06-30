#!/usr/bin/env python3
"""
Скрипт для исправления JWT аутентификации в targets.py
"""

import re

def fix_targets_file():
    """Исправление targets.py"""
    
    file_path = "backend/invite-service/app/api/v1/endpoints/targets.py"
    
    # Читаем файл
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Исправления для каждого endpoint
    fixes = [
        # create_targets_bulk
        (
            r'async def create_targets_bulk\(\s*task_id: int,\s*bulk_data: InviteTargetBulkCreate,\s*db: Session = Depends\(get_db\)\s*\):\s*"""Массовое создание целевых контактов"""\s*user_id = get_current_user_id\(\)',
            'async def create_targets_bulk(\n    task_id: int,\n    bulk_data: InviteTargetBulkCreate,\n    db: Session = Depends(get_db),\n    user_id: int = Depends(get_current_user_id)\n):\n    """Массовое создание целевых контактов"""'
        ),
        
        # get_targets
        (
            r'async def get_targets\((.*?)\):\s*"""Получение списка целевых контактов задачи"""\s*user_id = get_current_user_id\(\)',
            'async def get_targets(\\1,\n    user_id: int = Depends(get_current_user_id)\n):\n    """Получение списка целевых контактов задачи"""'
        ),
        
        # get_target
        (
            r'async def get_target\(\s*task_id: int,\s*target_id: int,\s*db: Session = Depends\(get_db\)\s*\):\s*"""Получение конкретного целевого контакта"""\s*user_id = get_current_user_id\(\)',
            'async def get_target(\n    task_id: int,\n    target_id: int,\n    db: Session = Depends(get_db),\n    user_id: int = Depends(get_current_user_id)\n):\n    """Получение конкретного целевого контакта"""'
        ),
        
        # update_target  
        (
            r'async def update_target\(\s*task_id: int,\s*target_id: int,\s*target_update: InviteTargetUpdate,\s*db: Session = Depends\(get_db\)\s*\):\s*"""Обновление целевого контакта"""\s*user_id = get_current_user_id\(\)',
            'async def update_target(\n    task_id: int,\n    target_id: int,\n    target_update: InviteTargetUpdate,\n    db: Session = Depends(get_db),\n    user_id: int = Depends(get_current_user_id)\n):\n    """Обновление целевого контакта"""'
        ),
        
        # delete_target
        (
            r'async def delete_target\(\s*task_id: int,\s*target_id: int,\s*db: Session = Depends\(get_db\)\s*\):\s*"""Удаление целевого контакта"""\s*user_id = get_current_user_id\(\)',
            'async def delete_target(\n    task_id: int,\n    target_id: int,\n    db: Session = Depends(get_db),\n    user_id: int = Depends(get_current_user_id)\n):\n    """Удаление целевого контакта"""'
        ),
        
        # bulk_target_operations
        (
            r'async def bulk_target_operations\(\s*task_id: int,\s*bulk_request: TargetBulkRequest,\s*db: Session = Depends\(get_db\)\s*\):\s*"""Массовые операции с целевыми контактами"""\s*user_id = get_current_user_id\(\)',
            'async def bulk_target_operations(\n    task_id: int,\n    bulk_request: TargetBulkRequest,\n    db: Session = Depends(get_db),\n    user_id: int = Depends(get_current_user_id)\n):\n    """Массовые операции с целевыми контактами"""'
        ),
        
        # get_target_stats
        (
            r'async def get_target_stats\(\s*task_id: int,\s*db: Session = Depends\(get_db\)\s*\):\s*"""Получение статистики по целевым контактам задачи"""\s*user_id = get_current_user_id\(\)',
            'async def get_target_stats(\n    task_id: int,\n    db: Session = Depends(get_db),\n    user_id: int = Depends(get_current_user_id)\n):\n    """Получение статистики по целевым контактам задачи"""'
        )
    ]
    
    # Применяем исправления
    for pattern, replacement in fixes:
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)
    
    # Записываем исправленный файл
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ targets.py исправлен!")

if __name__ == "__main__":
    fix_targets_file() 