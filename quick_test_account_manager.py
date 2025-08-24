#!/usr/bin/env python3
"""
Быстрое тестирование основных функций Account Manager
"""

import asyncio
import httpx
import json
from datetime import datetime

async def quick_test_account_manager():
    """Быстрый тест основных функций Account Manager"""
    base_url = "http://localhost:8001/api/v1/account-manager"
    
    print("🚀 Быстрое тестирование Account Manager")
    print("=" * 50)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # 1. Проверка статистики восстановления
        print("1. 📊 Проверка статистики восстановления...")
        try:
            response = await client.get(f"{base_url}/stats/recovery")
            if response.status_code == 200:
                stats = response.json()
                print(f"   ✅ Всего аккаунтов: {stats.get('total_accounts', 0)}")
                print(f"   ✅ Здоровых: {stats.get('healthy_accounts', 0)}")
                print(f"   ✅ В восстановлении: {stats.get('accounts_in_recovery', 0)}")
            else:
                print(f"   ❌ Ошибка: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
        
        # 2. Выделение аккаунта
        print("\n2. 🔍 Выделение тестового аккаунта...")
        allocation = None
        try:
            response = await client.post(f"{base_url}/allocate", json={
                "user_id": 1,
                "purpose": "testing",
                "service_name": "test-service",
                "timeout_minutes": 10
            })
            
            if response.status_code == 200:
                allocation = response.json()
                account_id = allocation['account_id']
                phone = allocation.get('phone', 'Не указан')
                print(f"   ✅ Аккаунт выделен: {account_id}")
                print(f"   📱 Телефон: {phone}")
                print(f"   ⏰ Истекает: {allocation.get('expires_at')}")
            else:
                print(f"   ❌ Ошибка выделения: {response.status_code}")
                print(f"   📝 Ответ: {response.text}")
                
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
        
        if allocation:
            account_id = allocation['account_id']
            
            # 3. Проверка здоровья аккаунта
            print(f"\n3. 🏥 Проверка здоровья аккаунта {account_id}...")
            try:
                response = await client.get(f"{base_url}/health/{account_id}")
                if response.status_code == 200:
                    health = response.json()
                    print(f"   ✅ Здоров: {health.get('is_healthy')}")
                    print(f"   📊 Статус: {health.get('status')}")
                    issues = health.get('issues', [])
                    if issues:
                        print(f"   ⚠️ Проблемы: {', '.join(issues)}")
                else:
                    print(f"   ❌ Ошибка проверки здоровья: {response.status_code}")
            except Exception as e:
                print(f"   ❌ Ошибка: {e}")
            
            # 4. Проверка rate limits
            print(f"\n4. ⏱️ Проверка rate limits для {account_id}...")
            try:
                response = await client.post(f"{base_url}/rate-limit/check/{account_id}", json={
                    "action_type": "invite",
                    "target_channel_id": "@testchannel"
                })
                
                if response.status_code == 200:
                    check_result = response.json()
                    print(f"   ✅ Действие разрешено: {check_result.get('allowed')}")
                    
                    checks = check_result.get('checks', {})
                    daily = checks.get('daily', {})
                    if daily:
                        print(f"   📈 Дневной лимит: {daily.get('used')}/{daily.get('limit')} "
                              f"(осталось: {daily.get('remaining')})")
                        
                else:
                    print(f"   ❌ Ошибка проверки лимитов: {response.status_code}")
            except Exception as e:
                print(f"   ❌ Ошибка: {e}")
            
            # 5. Запись тестового действия
            print(f"\n5. 📝 Запись тестового действия для {account_id}...")
            try:
                response = await client.post(f"{base_url}/rate-limit/record/{account_id}", json={
                    "action_type": "invite",
                    "target_channel_id": "@testchannel", 
                    "success": True
                })
                
                if response.status_code == 200:
                    record_result = response.json()
                    print(f"   ✅ Действие записано: {record_result.get('recorded')}")
                    
                    updated_counters = record_result.get('updated_counters', {})
                    if updated_counters:
                        print(f"   📊 Обновлено: invites_today={updated_counters.get('used_invites_today')}")
                        
                else:
                    print(f"   ❌ Ошибка записи действия: {response.status_code}")
            except Exception as e:
                print(f"   ❌ Ошибка: {e}")
            
            # 6. Получение статуса лимитов
            print(f"\n6. 📊 Получение полного статуса лимитов для {account_id}...")
            try:
                response = await client.get(f"{base_url}/rate-limit/status/{account_id}")
                if response.status_code == 200:
                    status = response.json()
                    daily_limits = status.get('daily_limits', {})
                    
                    print("   📈 Дневные лимиты:")
                    for action, limits in daily_limits.items():
                        used = limits.get('used', 0)
                        limit = limits.get('limit', 0)
                        remaining = limits.get('remaining', 0)
                        print(f"      • {action}: {used}/{limit} (осталось: {remaining})")
                    
                    per_channel = status.get('per_channel_limits', {})
                    if per_channel:
                        print("   🎯 Per-channel лимиты:")
                        for channel, stats in per_channel.items():
                            today = stats.get('used_today', 0)
                            total = stats.get('total_sent', 0) 
                            print(f"      • {channel}: сегодня={today}, всего={total}")
                            
                else:
                    print(f"   ❌ Ошибка получения статуса: {response.status_code}")
            except Exception as e:
                print(f"   ❌ Ошибка: {e}")
            
            # 7. Освобождение аккаунта
            print(f"\n7. 🔓 Освобождение аккаунта {account_id}...")
            try:
                response = await client.post(f"{base_url}/release/{account_id}", json={
                    "service_name": "test-service",
                    "usage_stats": {
                        "invites_sent": 1,
                        "messages_sent": 0,
                        "contacts_added": 0,
                        "channels_used": ["@testchannel"],
                        "success": True,
                        "error_type": None,
                        "error_message": None
                    }
                })
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"   ✅ Аккаунт освобожден: {result.get('success')}")
                    
                    updated_usage = result.get('updated_usage', {})
                    if updated_usage:
                        print(f"   📊 Итоговая статистика:")
                        print(f"      • Приглашений сегодня: {updated_usage.get('used_invites_today')}")
                        print(f"      • Сообщений сегодня: {updated_usage.get('used_messages_today')}")
                        
                else:
                    print(f"   ❌ Ошибка освобождения: {response.status_code}")
            except Exception as e:
                print(f"   ❌ Ошибка: {e}")
        
        print("\n" + "=" * 50)
        print("✅ Быстрое тестирование завершено!")

if __name__ == "__main__":
    asyncio.run(quick_test_account_manager())