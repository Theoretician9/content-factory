# Тестирование интеграции Account Manager с сервисами

## 🎯 Обзор

Этот документ содержит инструкции по тестированию интеграции Account Manager с Parsing Service и Invite Service. Account Manager обеспечивает централизованное управление Telegram аккаунтами для всех сервисов проекта.

## 📋 Подготовка к тестированию

### 1. Проверка запущенных сервисов

Убедитесь, что запущены все необходимые сервисы:

```bash
# Проверка статуса сервисов
docker-compose ps

# Должны быть запущены:
# - integration-service (8001)
# - parsing-service (8003) 
# - invite-service (8002)
# - mysql, postgresql, redis, rabbitmq
```

### 2. Проверка доступности Account Manager

```bash
# Проверка health endpoint
curl http://localhost:8001/health

# Проверка статистики восстановления
curl http://localhost:8001/api/v1/account-manager/stats/recovery
```

## 🧪 Тестовые скрипты

### Быстрое тестирование основных функций

```bash
# Запуск быстрого теста
python quick_test_account_manager.py
```

Этот скрипт проверяет:
- ✅ Статистику восстановления аккаунтов
- ✅ Выделение и освобождение аккаунта
- ✅ Проверку здоровья аккаунта
- ✅ Rate limiting функциональность
- ✅ Запись действий и обновление счетчиков

### Комплексное тестирование интеграции

```bash
# Запуск полного набора тестов
python test_account_manager_integration.py
```

Этот скрипт проверяет:
- 🔍 Базовую функциональность Account Manager
- 📊 Интеграцию с Parsing Service
- 📨 Интеграцию с Invite Service  
- 🔢 Per-channel limits (200 на канал)
- ⚠️ Обработку ошибок Telegram API
- 🔓 Освобождение аккаунтов и статистику

## 🔍 Ручное тестирование API

### 1. Выделение аккаунта

```bash
curl -X POST http://localhost:8001/api/v1/account-manager/allocate \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "purpose": "invite_campaign", 
    "service_name": "test-service",
    "timeout_minutes": 30
  }'
```

**Ожидаемый результат:**
```json
{
  "account_id": "uuid",
  "phone": "+1234567890",
  "allocated_at": "2025-08-24T12:00:00Z",
  "expires_at": "2025-08-24T12:30:00Z",
  "limits": {
    "daily_invite_limit": 30,
    "max_per_channel_total": 200
  }
}
```

### 2. Проверка здоровья аккаунта

```bash
curl http://localhost:8001/api/v1/account-manager/health/{account_id}
```

**Ожидаемый результат:**
```json
{
  "account_id": "uuid",
  "is_healthy": true,
  "status": "active",
  "issues": ["Account is healthy"],
  "recovery_eta": null
}
```

### 3. Проверка rate limits

```bash
curl -X POST http://localhost:8001/api/v1/account-manager/rate-limit/check/{account_id} \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "invite",
    "target_channel_id": "@testchannel"
  }'
```

**Ожидаемый результат:**
```json
{
  "allowed": true,
  "checks": {
    "daily": {"used": 0, "limit": 30, "remaining": 30},
    "per_channel": {"used": 0, "limit": 15, "remaining": 15}
  }
}
```

### 4. Запись действия

```bash
curl -X POST http://localhost:8001/api/v1/account-manager/rate-limit/record/{account_id} \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "invite",
    "target_channel_id": "@testchannel",
    "success": true
  }'
```

### 5. Освобождение аккаунта

```bash
curl -X POST http://localhost:8001/api/v1/account-manager/release/{account_id} \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "test-service",
    "usage_stats": {
      "invites_sent": 5,
      "messages_sent": 0,
      "contacts_added": 0,
      "channels_used": ["@testchannel"],
      "success": true
    }
  }'
```

## 🔄 Тестирование интеграций сервисов

### Parsing Service Integration

```bash
# 1. Проверка доступности Parsing Service
curl http://localhost:8003/health

# 2. Создание задачи парсинга (должна использовать Account Manager)
curl -X POST http://localhost:8003/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "platform": "telegram", 
    "targets": ["@testchannel"],
    "config": {
      "message_limit": 10,
      "speed_config": "safe"
    }
  }'

# 3. Проверка статуса задачи
curl http://localhost:8003/api/v1/tasks/{task_id}
```

### Invite Service Integration

```bash
# 1. Проверка доступности Invite Service
curl http://localhost:8002/health

# 2. Создание кампании приглашений (должна использовать Account Manager)
curl -X POST http://localhost:8002/api/v1/campaigns \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "name": "Test Campaign",
    "platform": "telegram",
    "targets": [
      {"username": "test_user", "phone": "+1234567890"}
    ],
    "invite_data": {
      "group_id": "@testchannel",
      "message": "Test invite"
    }
  }'

# 3. Проверка статуса кампании
curl http://localhost:8002/api/v1/campaigns/{campaign_id}
```

## 🧩 Тестирование Per-Channel Limits

Account Manager автоматически переключается на новый аккаунт при достижении 200 приглашений в один канал:

```bash
# 1. Проверка текущих per-channel лимитов
curl http://localhost:8001/api/v1/account-manager/rate-limit/status/{account_id}

# 2. Симуляция приглашений в канал
for i in {1..5}; do
  curl -X POST http://localhost:8001/api/v1/account-manager/rate-limit/record/{account_id} \
    -H "Content-Type: application/json" \
    -d '{
      "action_type": "invite",
      "target_channel_id": "test_channel",
      "success": true
    }'
done

# 3. Проверка обновленной статистики
curl http://localhost:8001/api/v1/account-manager/rate-limit/status/{account_id}
```

**Ожидаемый результат:** В `per_channel_limits` должна появиться статистика для `test_channel`.

## ⚠️ Тестирование обработки ошибок

### FloodWaitError

```bash
curl -X POST http://localhost:8001/api/v1/account-manager/handle-error/{account_id} \
  -H "Content-Type: application/json" \
  -d '{
    "error_type": "flood_wait",
    "error_message": "FloodWaitError: 300",
    "context": {"service": "test-service"}
  }'
```

**Ожидаемый результат:** Аккаунт должен быть заблокирован на 300 + 60 секунд (с буфером).

### PeerFloodError

```bash
curl -X POST http://localhost:8001/api/v1/account-manager/handle-error/{account_id} \
  -H "Content-Type: application/json" \
  -d '{
    "error_type": "peer_flood", 
    "error_message": "PeerFloodError: Too many requests",
    "context": {"service": "test-service"}
  }'
```

**Ожидаемый результат:** Аккаунт должен быть заблокирован на 24 часа.

## 📊 Мониторинг и статистика

### Статистика восстановления

```bash
curl http://localhost:8001/api/v1/account-manager/stats/recovery
```

### Здоровье всех аккаунтов

```bash
# Получение списка всех аккаунтов и их здоровья
# (Если такой endpoint реализован)
curl http://localhost:8001/api/v1/account-manager/accounts/health
```

## 🐛 Отладка проблем

### Логи сервисов

```bash
# Логи Integration Service
docker-compose logs integration-service --tail 50

# Логи Parsing Service
docker-compose logs parsing-service --tail 50

# Логи Invite Service  
docker-compose logs invite-service --tail 50
```

### Проверка базы данных

```bash
# Подключение к PostgreSQL
docker exec -it html-postgresql-1 psql -U integration_user -d integration_db

# Проверка Account Manager полей
SELECT id, phone, status, locked, used_invites_today, used_messages_today, 
       per_channel_invites, error_count, last_used_at
FROM telegram_sessions 
WHERE is_active = true
LIMIT 10;
```

### Проверка Redis

```bash
# Подключение к Redis
docker exec -it html-redis-1 redis-cli

# Проверка locks (DB 1)
SELECT 1
KEYS account_lock:*

# Проверка recovery queue (DB 2)  
SELECT 2
ZRANGE account_recovery_queue 0 -1 WITHSCORES
```

## ✅ Критерии успешности

### Базовая функциональность
- [ ] Account Manager отвечает на все API запросы
- [ ] Аккаунты успешно выделяются и освобождаются
- [ ] Rate limiting работает корректно
- [ ] Per-channel limits соблюдаются (200 макс на канал)
- [ ] Ошибки обрабатываются правильно

### Интеграция с сервисами
- [ ] Parsing Service использует Account Manager для получения аккаунтов
- [ ] Invite Service использует Account Manager для управления аккаунтами
- [ ] Distributed locking работает между сервисами
- [ ] Статистика использования корректно обновляется

### Обработка ошибок
- [ ] FloodWaitError автоматически планирует восстановление
- [ ] PeerFloodError блокирует аккаунт на 24 часа
- [ ] AuthKeyError отключает аккаунт навсегда
- [ ] Все ошибки логируются в IntegrationLogService

## 🎯 Следующие шаги

После успешного тестирования интеграции:

1. **Настройка Background Workers** - для автоматического сброса лимитов и восстановления
2. **Grafana дашборды** - для мониторинга аккаунтов и метрик
3. **Production deployment** - деплой в продуктивную среду
4. **Нагрузочное тестирование** - проверка работы под высокой нагрузкой

---

## 📞 Поддержка

При возникновении проблем проверьте:
1. Статус всех сервисов в docker-compose
2. Логи соответствующих сервисов
3. Состояние базы данных и Redis
4. Корректность API запросов и данных