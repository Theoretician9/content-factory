#!/usr/bin/env python3
"""
Скрипт для отладки JWT токенов и проверки изоляции пользователей.
"""

import requests
import jwt
import json
from datetime import datetime, timedelta

# Конфигурация
API_BASE = "http://92.113.146.148:8000"
JWT_SECRET_API_GATEWAY = "your-jwt-secret"  # Значение по умолчанию в API Gateway
JWT_SECRET_INTEGRATION = "super-secret-jwt-key-for-content-factory-2024"  # Значение в Integration Service

def create_jwt_token(user_id: int, secret: str) -> str:
    """Создает JWT токен для пользователя с указанным секретом"""
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, secret, algorithm="HS256")

def decode_jwt_token(token: str, secret: str) -> dict:
    """Декодирует JWT токен с указанным секретом"""
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except Exception as e:
        return {"error": str(e)}

def test_jwt_secrets():
    """Тестирует JWT токены с разными секретами"""
    print("🔐 Тестирование JWT токенов...")
    
    # Тест 1: Создаем токены с разными секретами
    user1_token_api = create_jwt_token(1, JWT_SECRET_API_GATEWAY)
    user1_token_int = create_jwt_token(1, JWT_SECRET_INTEGRATION)
    
    print(f"\n👤 User 1 token (API Gateway secret): {user1_token_api[:50]}...")
    print(f"👤 User 1 token (Integration secret): {user1_token_int[:50]}...")
    
    # Тест 2: Декодируем токены
    print("\n🔍 Декодирование токенов:")
    print("API Gateway token с API Gateway secret:", decode_jwt_token(user1_token_api, JWT_SECRET_API_GATEWAY))
    print("API Gateway token с Integration secret:", decode_jwt_token(user1_token_api, JWT_SECRET_INTEGRATION))
    print("Integration token с API Gateway secret:", decode_jwt_token(user1_token_int, JWT_SECRET_API_GATEWAY))
    print("Integration token с Integration secret:", decode_jwt_token(user1_token_int, JWT_SECRET_INTEGRATION))

def test_real_login():
    """Тестирует реальный логин и получение токена"""
    print("\n🚪 Тестирование реального логина...")
    
    # Логинимся и получаем токен
    login_data = {
        "username": "test@example.com",
        "password": "testpassword123"
    }
    
    try:
        response = requests.post(f"{API_BASE}/api/auth/login", json=login_data)
        print(f"Login status: {response.status_code}")
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get("access_token")
            
            if access_token:
                print(f"Access token получен: {access_token[:50]}...")
                
                # Декодируем токен с разными секретами
                print("\n🔍 Декодирование реального токена:")
                payload_api = decode_jwt_token(access_token, JWT_SECRET_API_GATEWAY)
                payload_int = decode_jwt_token(access_token, JWT_SECRET_INTEGRATION)
                
                print(f"С API Gateway secret: {payload_api}")
                print(f"С Integration secret: {payload_int}")
                
                # Тестируем запрос к Integration Service
                headers = {"Authorization": f"Bearer {access_token}"}
                int_response = requests.get(f"{API_BASE}/api/integrations/telegram/accounts", headers=headers)
                print(f"\nЗапрос к Integration Service: {int_response.status_code}")
                if int_response.status_code == 200:
                    accounts = int_response.json()
                    print(f"Найдено аккаунтов: {len(accounts)}")
                    for acc in accounts:
                        print(f"  - Account: {acc.get('id', 'N/A')}, User ID: {acc.get('user_id', 'N/A')}")
                else:
                    print(f"Ошибка: {int_response.text}")
            else:
                print("Access token не найден в ответе")
        else:
            print(f"Ошибка логина: {response.text}")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")

def test_manual_tokens():
    """Тестирует с разными токенами вручную"""
    print("\n🧪 Тестирование с разными токенами...")
    
    # Создаем токены для разных пользователей с правильным секретом
    user1_token = create_jwt_token(1, JWT_SECRET_API_GATEWAY)
    user2_token = create_jwt_token(2, JWT_SECRET_API_GATEWAY)
    
    headers1 = {"Authorization": f"Bearer {user1_token}"}
    headers2 = {"Authorization": f"Bearer {user2_token}"}
    
    print(f"\n👤 User 1 token: {user1_token[:50]}...")
    print(f"👤 User 2 token: {user2_token[:50]}...")
    
    # Тестируем запросы
    try:
        print("\n📋 Запросы от user 1:")
        response1 = requests.get(f"{API_BASE}/api/integrations/telegram/accounts", headers=headers1)
        print(f"Status: {response1.status_code}")
        if response1.status_code == 200:
            accounts1 = response1.json()
            print(f"Аккаунтов для user 1: {len(accounts1)}")
            for acc in accounts1:
                print(f"  - User ID: {acc.get('user_id', 'N/A')}, Phone: {acc.get('phone', 'N/A')}")
        else:
            print(f"Ошибка: {response1.text}")
        
        print("\n📋 Запросы от user 2:")
        response2 = requests.get(f"{API_BASE}/api/integrations/telegram/accounts", headers=headers2)
        print(f"Status: {response2.status_code}")
        if response2.status_code == 200:
            accounts2 = response2.json()
            print(f"Аккаунтов для user 2: {len(accounts2)}")
            for acc in accounts2:
                print(f"  - User ID: {acc.get('user_id', 'N/A')}, Phone: {acc.get('phone', 'N/A')}")
        else:
            print(f"Ошибка: {response2.text}")
            
    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")

if __name__ == "__main__":
    test_jwt_secrets()
    test_real_login()
    test_manual_tokens()
    print("\n🎯 Тестирование завершено!") 