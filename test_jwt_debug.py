#!/usr/bin/env python3
"""
Диагностический скрипт для проверки JWT обработки Integration Service.
"""

import requests
import jwt
import json
from datetime import datetime, timedelta

# Конфигурация
API_BASE = "http://92.113.146.148:8000"
JWT_SECRET = "super-secret-jwt-key-for-content-factory-2024"

def create_jwt_token(user_id: int) -> str:
    """Создает JWT токен для пользователя"""
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def test_jwt_processing():
    """Тестирует обработку JWT токенов"""
    print("🧪 Диагностика JWT обработки...")
    
    # Создаем токены для разных пользователей
    tokens = {
        1: create_jwt_token(1),
        2: create_jwt_token(2),
        99: create_jwt_token(99)
    }
    
    for user_id, token in tokens.items():
        print(f"\n👤 Тест для user_id={user_id}")
        print(f"Token: {token[:50]}...")
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Тест 1: Проверяем debug-jwt endpoint (если есть)
        try:
            response = requests.get(f"{API_BASE}/debug-jwt", headers=headers)
            print(f"Debug JWT - Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                extracted_user_id = data.get("extracted_user_id")
                print(f"  Extracted user_id: {extracted_user_id}")
                if extracted_user_id == user_id:
                    print("  ✅ JWT обработка корректна")
                else:
                    print("  ❌ ОШИБКА JWT обработки!")
            else:
                print(f"  Error: {response.text}")
        except Exception as e:
            print(f"  ❌ Ошибка запроса debug-jwt: {e}")
        
        # Тест 2: Проверяем обычный accounts endpoint  
        try:
            response = requests.get(f"{API_BASE}/api/v1/telegram/accounts", headers=headers)
            print(f"Accounts - Status: {response.status_code}")
            if response.status_code == 200:
                accounts = response.json()
                print(f"  Найдено аккаунтов: {len(accounts)}")
                for acc in accounts:
                    acc_user_id = acc.get("user_id")
                    print(f"    Account {acc['id']}: user_id={acc_user_id}")
                    if acc_user_id != user_id:
                        print(f"    ❌ НАРУШЕНИЕ ИЗОЛЯЦИИ: ожидался user_id={user_id}, получен {acc_user_id}")
            else:
                print(f"  Error: {response.text}")
        except Exception as e:
            print(f"  ❌ Ошибка запроса accounts: {e}")

    # Дополнительный тест: проверяем без токена
    print(f"\n🔒 Тест без авторизации")
    try:
        response = requests.get(f"{API_BASE}/api/v1/telegram/accounts")
        print(f"No auth - Status: {response.status_code}")
        if response.status_code == 401:
            print("  ✅ Правильно блокируется неавторизованный доступ")
        else:
            print(f"  ❌ Неожиданный ответ: {response.text}")
    except Exception as e:
        print(f"  ❌ Ошибка запроса: {e}")

if __name__ == "__main__":
    test_jwt_processing() 