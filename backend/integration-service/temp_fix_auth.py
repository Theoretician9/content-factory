#!/usr/bin/env python3
"""
Временный фикс для авторизации в Integration Service.
Заменяет get_user_id_from_request на версию с hardcoded user_id = 1.
"""

# Временное содержимое для замены в app/core/auth.py
TEMP_AUTH_FUNCTION = '''
async def get_user_id_from_request(request: Request) -> int:
    """
    ВРЕМЕННАЯ функция авторизации - возвращает user_id = 1 для всех запросов.
    TODO: Исправить JWT секреты для правильной изоляции пользователей.
    """
    # ВРЕМЕННОЕ РЕШЕНИЕ: Принудительно используем user_id = 1
    logger.error("⚠️ TEMPORARY FIX: Using hardcoded user_id = 1 for all requests")
    return 1
'''

print("Для исправления авторизации нужно:")
print("1. Найти правильный JWT секрет в основной системе")
print("2. Синхронизировать секреты между сервисами")
print("3. Или временно использовать hardcoded user_id = 1") 