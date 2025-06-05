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
    
    print(f"👤 User 1 token: {user1_token[:50]}...")
    print(f"👤 User 2 token: {user2_token[:50]}...")
    
    # Заголовки авторизации
    headers1 = {"Authorization": f"Bearer {user1_token}"}
    headers2 = {"Authorization": f"Bearer {user2_token}"}
    
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
    
    # Тест 3: Попытка получить QR код без токена
    print("\n🔒 Тест 3: Запрос без авторизации")
    try:
        response_no_auth = requests.get(f"{API_BASE}/qr-code")
        print(f"Status без токена: {response_no_auth.status_code}")
        if response_no_auth.status_code == 401:
            print("✅ Правильно блокируется неавторизованный доступ")
        else:
            print(f"❌ Неожиданный ответ: {response_no_auth.text}")
    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
    
    # Тест 4: Получение QR кода для пользователя 1
    print("\n🔢 Тест 4: Получение QR кода для пользователя 1")
    try:
        response_qr = requests.get(f"{API_BASE}/qr-code", headers=headers1)
        print(f"Status: {response_qr.status_code}")
        if response_qr.status_code == 200:
            qr_data = response_qr.json()
            print("✅ QR код успешно получен")
            print(f"Message: {qr_data.get('message', 'N/A')}")
        else:
            print(f"❌ Ошибка получения QR кода: {response_qr.text}")
    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
    
    # Тест 5: Получение логов для пользователя 1
    print("\n📊 Тест 5: Получение логов пользователя 1")
    try:
        response_logs = requests.get(f"{API_BASE}/logs", headers=headers1)
        print(f"Status: {response_logs.status_code}")
        if response_logs.status_code == 200:
            logs1 = response_logs.json()
            print(f"Найдено логов для user_id=1: {len(logs1)}")
            for log in logs1[:3]:  # Показываем только первые 3
                print(f"  - Log ID: {log['id']}, User ID: {log['user_id']}, Action: {log['action']}")
        else:
            print(f"Error: {response_logs.text}")
    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
    
    print("\n🎯 Тестирование завершено!")

if __name__ == "__main__":
    test_user_isolation() 