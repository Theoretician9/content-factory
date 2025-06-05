#!/usr/bin/env python3
"""
Скрипт для тестирования JWT аутентификации Integration Service
"""

import requests
import jwt
from datetime import datetime, timedelta

# Конфигурация
API_BASE = "http://92.113.146.148:8000"
JWT_SECRET = "super-secret-jwt-key-for-content-factory-2024"  # Значение по умолчанию из docker-compose

def create_test_token(user_id: int) -> str:
    """Создает тестовый JWT токен"""
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def test_auth():
    """Тестирует авторизацию в Integration Service"""
    print("🔐 Тестирование JWT авторизации...")
    
    # Создаем токены для разных пользователей
    user1_token = create_test_token(1)
    user2_token = create_test_token(999)  # Пользователь которого точно нет
    
    print(f"User 1 token: {user1_token[:50]}...")
    print(f"User 999 token: {user2_token[:50]}...")
    
    # Тестируем запросы с токенами
    headers1 = {"Authorization": f"Bearer {user1_token}"}
    headers2 = {"Authorization": f"Bearer {user2_token}"}
    
    print(f"\n📋 Тест 1: Запрос аккаунтов от user_id=1")
    try:
        response1 = requests.get(f"{API_BASE}/api/integrations/telegram/accounts", headers=headers1)
        print(f"Status: {response1.status_code}")
        if response1.status_code == 200:
            accounts1 = response1.json()
            print(f"Найдено аккаунтов: {len(accounts1)}")
            for acc in accounts1:
                print(f"  - Account {acc['id'][:8]}..., user_id: {acc['user_id']}, phone: {acc['phone']}")
        else:
            print(f"Ошибка: {response1.text}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    
    print(f"\n📋 Тест 2: Запрос аккаунтов от user_id=999")
    try:
        response2 = requests.get(f"{API_BASE}/api/integrations/telegram/accounts", headers=headers2)
        print(f"Status: {response2.status_code}")
        if response2.status_code == 200:
            accounts2 = response2.json()
            print(f"Найдено аккаунтов: {len(accounts2)}")
            for acc in accounts2:
                print(f"  - Account {acc['id'][:8]}..., user_id: {acc['user_id']}, phone: {acc['phone']}")
        else:
            print(f"Ошибка: {response2.text}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    
    # Тест без токена
    print(f"\n🚫 Тест 3: Запрос без токена")
    try:
        response3 = requests.get(f"{API_BASE}/api/integrations/telegram/accounts")
        print(f"Status: {response3.status_code}")
        print(f"Response: {response3.text}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    test_auth()
    print("\n🎯 Тестирование завершено!") 