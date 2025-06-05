#!/usr/bin/env python3
import jwt
import requests

# Используем правильный секрет из docker-compose
JWT_SECRET = "super-secret-jwt-key-for-content-factory-2024"

# Создаем токен для user 1
token = jwt.encode({'sub': '1', 'exp': 9999999999}, JWT_SECRET, algorithm='HS256')
print('Token for user 1:', token[:50] + '...')

# Тест с токеном
headers = {'Authorization': f'Bearer {token}'}
resp = requests.get('http://92.113.146.148:8000/api/integrations/telegram/accounts', headers=headers)
print('Status with token:', resp.status_code)
print('Response:', resp.json())

# Тест без токена
resp2 = requests.get('http://92.113.146.148:8000/api/integrations/telegram/accounts')
print('Status without token:', resp2.status_code)
print('Response without token:', resp2.json()) 