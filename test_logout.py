#!/usr/bin/env python3
import requests
import json

# Базовый URL API Gateway
BASE_URL = "http://92.113.146.148:8000/api"

def test_logout_flow():
    """Тестируем полный поток login -> logout"""
    print("🔐 Начинаем тест logout функциональности...")
    
    # 1. Логинимся для получения токенов
    print("\n1. Выполняем логин...")
    # Используем JSON формат как в веб интерфейсе
    login_data = {
        "username": "nikita.f3d@gmail.com", 
        "password": "LTB8T9pFhDiipYm"
    }
    
    try:
        login_response = requests.post(
            f"{BASE_URL}/auth/login",
            json=login_data,  # Используем JSON вместо form data
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"Login response status: {login_response.status_code}")
        print(f"Login response headers: {dict(login_response.headers)}")
        print(f"Login response cookies: {dict(login_response.cookies)}")
        
        if login_response.status_code != 200:
            print(f"❌ Ошибка логина: {login_response.status_code} - {login_response.text}")
            return
        
        login_result = login_response.json()
        print(f"Login response body: {login_result}")
        
        access_token = login_result["access_token"]
        
        # Сохраняем cookies (включая refresh_token)
        cookies = login_response.cookies
        print(f"✅ Логин успешен, получен access_token: {access_token[:20]}...")
        print(f"✅ Cookies: {dict(cookies)}")
        
    except Exception as e:
        print(f"❌ Ошибка при логине: {e}")
        return
    
    # 2. Проверяем доступ к защищенному ресурсу
    print("\n2. Проверяем доступ к /auth/me...")
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        me_response = requests.get(f"{BASE_URL}/auth/me", headers=headers, timeout=10)
        print(f"Me response status: {me_response.status_code}")
        if me_response.status_code == 200:
            print(f"✅ Доступ к /auth/me разрешен: {me_response.json()}")
        else:
            print(f"❌ Ошибка доступа к /auth/me: {me_response.status_code} - {me_response.text}")
    except Exception as e:
        print(f"❌ Ошибка при запросе /auth/me: {e}")
    
    # 3. Выполняем logout
    print("\n3. Выполняем logout...")
    try:
        logout_response = requests.post(
            f"{BASE_URL}/auth/logout",
            headers=headers,
            cookies=cookies,
            timeout=10
        )
        
        print(f"Logout response status: {logout_response.status_code}")
        print(f"Logout response headers: {dict(logout_response.headers)}")
        print(f"Logout response cookies: {dict(logout_response.cookies)}")
        
        if logout_response.status_code == 200:
            print(f"✅ Logout успешен: {logout_response.json()}")
            # Обновляем cookies после logout
            cookies.update(logout_response.cookies)
            print(f"✅ Обновленные cookies: {dict(cookies)}")
        else:
            print(f"❌ Ошибка logout: {logout_response.status_code} - {logout_response.text}")
            return
            
    except Exception as e:
        print(f"❌ Ошибка при logout: {e}")
        return
    
    # 4. Проверяем что доступ заблокирован после logout
    print("\n4. Проверяем доступ к /auth/me после logout...")
    try:
        me_response_after = requests.get(f"{BASE_URL}/auth/me", headers=headers, timeout=10)
        
        print(f"Me after logout response status: {me_response_after.status_code}")
        if me_response_after.status_code == 401:
            print("✅ Доступ к /auth/me заблокирован после logout (токен в blacklist)")
        elif me_response_after.status_code == 200:
            print("⚠️ Доступ к /auth/me все еще разрешен (возможная проблема)")
            print(f"Response: {me_response_after.json()}")
        else:
            print(f"❓ Неожиданный ответ: {me_response_after.status_code} - {me_response_after.text}")
    except Exception as e:
        print(f"❌ Ошибка при проверке /auth/me после logout: {e}")
    
    # 5. Проверяем повторный logout с теми же токенами
    print("\n5. Проверяем повторный logout...")
    try:
        logout_response2 = requests.post(
            f"{BASE_URL}/auth/logout",
            headers=headers,
            cookies=cookies,
            timeout=10
        )
        
        print(f"Second logout response status: {logout_response2.status_code}")
        if logout_response2.status_code == 200:
            print(f"✅ Повторный logout прошел: {logout_response2.json()}")
        else:
            print(f"❌ Ошибка повторного logout: {logout_response2.status_code} - {logout_response2.text}")
    except Exception as e:
        print(f"❌ Ошибка при повторном logout: {e}")

if __name__ == "__main__":
    test_logout_flow() 