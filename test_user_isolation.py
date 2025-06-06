#!/usr/bin/env python3
"""
Тестовый скрипт для проверки изоляции пользователей в Integration Service.
Проверяет, что каждый пользователь видит только свои интеграции.
"""

import requests
import jwt
import json
from datetime import datetime, timedelta

# Конфигурация
API_BASE = "http://92.113.146.148:8000/api/integrations/telegram"
JWT_SECRET = "super-secret-jwt-key-for-content-factory-2024"

def create_jwt_token(user_id: int) -> str:
    """Создает JWT токен для пользователя"""
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def test_user_isolation():
    """Тестирует изоляцию пользователей"""
    print("🧪 Тестирование изоляции пользователей Integration Service...")
    
    # Создаем токены для двух разных пользователей
    user1_token = create_jwt_token(1)
    user2_token = create_jwt_token(2)
    user99_token = create_jwt_token(99)
    
    print(f"👤 User 1 token: {user1_token[:50]}...")
    print(f"👤 User 2 token: {user2_token[:50]}...")
    print(f"👤 User 99 token: {user99_token[:50]}...")
    
    # Заголовки авторизации
    headers1 = {"Authorization": f"Bearer {user1_token}"}
    headers2 = {"Authorization": f"Bearer {user2_token}"}
    headers99 = {"Authorization": f"Bearer {user99_token}"}
    
    # Тест 1: Получение аккаунтов для пользователя 1
    print("\n📋 Тест 1: Получение аккаунтов пользователя 1")
    try:
        response1 = requests.get(f"{API_BASE}/accounts", headers=headers1)
        print(f"Status: {response1.status_code}")
        if response1.status_code == 200:
            accounts1 = response1.json()
            print(f"Найдено аккаунтов для user_id=1: {len(accounts1)}")
            for acc in accounts1:
                print(f"  - Account ID: {acc['id']}, User ID: {acc['user_id']}, Phone: {acc['phone']}")
        else:
            print(f"Error: {response1.text}")
    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
    
    # Тест 2: Получение аккаунтов для пользователя 2
    print("\n📋 Тест 2: Получение аккаунтов пользователя 2")
    try:
        response2 = requests.get(f"{API_BASE}/accounts", headers=headers2)
        print(f"Status: {response2.status_code}")
        if response2.status_code == 200:
            accounts2 = response2.json()
            print(f"Найдено аккаунтов для user_id=2: {len(accounts2)}")
            for acc in accounts2:
                print(f"  - Account ID: {acc['id']}, User ID: {acc['user_id']}, Phone: {acc['phone']}")
        else:
            print(f"Error: {response2.text}")
    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
    
    # Тест 3: Получение аккаунтов для пользователя 99
    print("\n📋 Тест 3: Получение аккаунтов пользователя 99")
    try:
        response99 = requests.get(f"{API_BASE}/accounts", headers=headers99)
        print(f"Status: {response99.status_code}")
        if response99.status_code == 200:
            accounts99 = response99.json()
            print(f"Найдено аккаунтов для user_id=99: {len(accounts99)}")
            for acc in accounts99:
                print(f"  - Account ID: {acc['id']}, User ID: {acc['user_id']}, Phone: {acc['phone']}")
        else:
            print(f"Error: {response99.text}")
    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
    
    # Тест 4: Тестирование auth endpoint
    print("\n🔐 Тест 4: Проверка извлечения user_id из токенов")
    for i, (user_id, headers) in enumerate([(1, headers1), (2, headers2), (99, headers99)], 1):
        try:
            response = requests.get(f"{API_BASE}/test-auth", headers=headers)
            print(f"Test {i} - Expected user_id={user_id}, Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                extracted_user_id = data.get("authenticated_user_id")
                print(f"  Extracted user_id: {extracted_user_id}")
                if extracted_user_id == user_id:
                    print("  ✅ Корректная изоляция пользователей")
                else:
                    print("  ❌ ОШИБКА ИЗОЛЯЦИИ!")
            else:
                print(f"  Error: {response.text}")
        except Exception as e:
            print(f"  ❌ Ошибка запроса: {e}")

    # Анализ результатов
    print("\n📊 Анализ изоляции пользователей:")
    print("Если пользователи видят одинаковые аккаунты - есть проблема с изоляцией.")
    print("Каждый пользователь должен видеть только свои Telegram аккаунты.")

if __name__ == "__main__":
    test_user_isolation() 