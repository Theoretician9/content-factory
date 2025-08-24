# Account Manager Implementation - Complete Production Guide

## Обзор

Account Manager - это централизованная система управления Telegram аккаунтами для всех сервисов проекта Content Factory. Система обеспечивает:

- 🎯 **Централизованное распределение аккаунтов** между сервисами (Invite, Parsing, Messaging)
- 🛡️ **Строгое соблюдение лимитов** Telegram API (30 приглашений/день, 30 сообщений/день, 15 контактов/день)
- 🔄 **Per-channel limits**: Максимум 200 приглашений на канал с одного аккаунта (автосмена аккаунтов)
- ⚡ **Автоматическое восстановление** после флуд-ожиданий и банов
- 🔒 **Distributed locking** для предотвращения конфликтов
- 📊 **Мониторинг и логирование** всех операций
- 🛠️ **Production-ready** с полным error handling

## Архитектура системы

### Основные компоненты

1. **AccountManagerService** - Центральный сервис для выделения и освобождения аккаунтов с оптимальным выбором
2. **RateLimitingService** - Контроль лимитов Telegram API с burst логикой и cooldown
3. **FloodBanManager** - Управление флуд-ожиданиями и автоматическое восстановление
4. **Background Workers** - Фоновые задачи для maintenance и мониторинга (Celery)
5. **API Endpoints** - 12 REST API endpoints для взаимодействия с другими сервисами

### База данных

Расширена существующая таблица `telegram_sessions` с полями Account Manager:

```sql
-- Account Manager поля
status VARCHAR(20) DEFAULT 'active',
locked BOOLEAN DEFAULT FALSE,
locked_by VARCHAR(100),
locked_until TIMESTAMPTZ,

-- Лимиты и счетчики
used_invites_today INTEGER DEFAULT 0,
used_messages_today INTEGER DEFAULT 0,
contacts_today INTEGER DEFAULT 0,
per_channel_invites JSONB DEFAULT '{}',

-- Управление ошибками
error_count INTEGER DEFAULT 0,
flood_wait_until TIMESTAMPTZ,
blocked_until TIMESTAMPTZ,
last_used_at TIMESTAMPTZ
```

### Redis структуры

Account Manager использует отдельные Redis базы данных:

- **DB+1**: Distributed locks для аккаунтов (`account_lock:{account_id}`)
- **DB+2**: Очереди восстановления и flood/ban management
- **DB+3**: Rate limiting данные (hourly limits, cooldowns, burst tracking)
- **DB+4**: Celery broker и backend для workers

## Telegram API Limits - Business Rules

### Основные лимиты (соответствуют требованиям)

```python
# Конфигурация лимитов в RateLimitingService
telegram_limits = {
    ActionType.INVITE: {
        'daily_limit': 30,         # 30 приглашений в день
        'hourly_limit': 2,         # 2 приглашения в час (равномерность)
        'per_channel_daily': 15,   # 15 приглашений в день на канал
        'cooldown_seconds': 900,   # 15 минут между приглашениями
        'burst_limit': 3,          # Максимум 3 приглашения подряд
        'burst_cooldown': 900      # 15 минут после burst
    },
    ActionType.MESSAGE: {
        'daily_limit': 30,         # 30 сообщений в день
        'hourly_limit': 10,        # 10 сообщений в час
        'cooldown_seconds': 60,    # 1 минута между сообщениями
        'burst_limit': 5,          # Максимум 5 сообщений подряд
        'burst_cooldown': 180      # 3 минуты после burst
    },
    ActionType.ADD_CONTACT: {
        'daily_limit': 15,         # 15 контактов в день
        'hourly_limit': 3,         # 3 контакта в час
        'cooldown_seconds': 300,   # 5 минут между добавлениями
        'burst_limit': 2,          # Максимум 2 контакта подряд
        'burst_cooldown': 600      # 10 минут после burst
    }
}
```

### Per-Channel Logic (200 максимум на канал)

**ВАЖНО**: 200 максимум на канал с ОДНОГО аккаунта. Для 1000 приглашений в канал нужно 5 аккаунтов:

```python
# Структура per_channel_invites в PostgreSQL:
{
  "channel_123": {
    "today": 5,     // приглашений сегодня в этот канал
    "total": 150    // всего приглашений в этот канал с этого аккаунта
  },
  "channel_456": {
    "today": 3,
    "total": 50
  }
}

# Автоматическая смена аккаунта:
@property
def max_per_channel_total(self) -> int:
    """Максимум инвайтов на один канал (всего)"""
    return 200

def can_send_invite(self, channel_id: str = None) -> bool:
    # Проверка лимита по каналу
    if channel_id:
        channel_total = self.per_channel_invites.get(channel_id, {}).get('total', 0)
        if channel_total >= self.max_per_channel_total:  # >= 200
            return False  # Account Manager выделит следующий аккаунт
    return True
```

### Error Handling & Recovery

```python
# Обработка ошибок Telegram API
class ErrorType(str, Enum):
    FLOOD_WAIT = "flood_wait"          # Автоматическое ожидание + 1 минута буфер
    PEER_FLOOD = "peer_flood"          # 24 часа блокировки
    PHONE_NUMBER_BANNED = "phone_number_banned"  # Permanent disable
    USER_DEACTIVATED = "user_deactivated"        # Permanent disable
    AUTH_KEY_ERROR = "auth_key_error"             # Permanent disable

# Логика обработки в handle_account_error:
if error_type == ErrorType.FLOOD_WAIT:
    # Извлекаем секунды из "FloodWaitError: 300"
    seconds = extract_seconds_from_message(error_message)
    recovery_time = now + timedelta(seconds=seconds + 60)  # +1 минута буфер
    new_status = AccountStatus.FLOOD_WAIT
    
elif error_type == ErrorType.PEER_FLOOD:
    recovery_time = now + timedelta(hours=24)  # 24 часа
    new_status = AccountStatus.BLOCKED
```

## API Endpoints

### Базовые операции

#### Выделение аккаунта
```http
POST /api/v1/account-manager/allocate
Content-Type: application/json

{
  "user_id": 123,
  "purpose": "invite_campaign",
  "service_name": "invite-service",
  "preferred_account_id": "uuid-optional",
  "timeout_minutes": 30
}
```

#### Освобождение аккаунта
```http
POST /api/v1/account-manager/release/{account_id}
Content-Type: application/json

{
  "service_name": "invite-service",
  "usage_stats": {
    "invites_sent": 5,
    "messages_sent": 0,
    "contacts_added": 0,
    "success": true,
    "channels_used": ["channel_id_1"]
  }
}
```

#### Обработка ошибки
```http
POST /api/v1/account-manager/handle-error/{account_id}
Content-Type: application/json

{
  "error_type": "flood_wait",
  "error_message": "FloodWaitError: 300",
  "context": {
    "service": "invite-service"
  }
}
```

### Мониторинг и статистика

#### Проверка здоровья аккаунта
```http
GET /api/v1/account-manager/health/{account_id}
```

#### Статус лимитов
```http
GET /api/v1/account-manager/rate-limit/status/{account_id}
```

#### Статистика восстановления
```http
GET /api/v1/account-manager/stats/recovery
```

### Rate Limiting API

#### Проверка лимитов
```http
POST /api/v1/account-manager/rate-limit/check/{account_id}
Content-Type: application/json

{
  "action_type": "invite",
  "target_channel_id": "channel_123"
}
```

#### Запись действия
```http
POST /api/v1/account-manager/rate-limit/record/{account_id}
Content-Type: application/json

{
  "action_type": "invite",
  "target_channel_id": "channel_123",
  "success": true
}
```

## Background Workers

### Периодические задачи

1. **Восстановление аккаунтов** (каждые 5 минут)
   - Обрабатывает очередь запланированных восстановлений
   - Снимает истекшие flood wait и блокировки

2. **Сброс дневных лимитов** (в полночь UTC)
   - Обнуляет `used_invites_today`, `used_messages_today`, `contacts_today`
   - Очищает `per_channel_invites`

3. **Мониторинг здоровья** (каждые 15 минут)
   - Проверяет проблемные аккаунты
   - Автоматически планирует восстановление

4. **Очистка устаревших данных** (каждые 30 минут - 1 час)
   - Удаляет истекшие блокировки
   - Очищает старые rate limiting данные

5. **Генерация отчетов** (каждые 6 часов)
   - Создает отчеты о состоянии системы
   - Формирует алерты при проблемах

### Запуск workers

```bash
# Worker для обработки задач
python -m celery -A app.workers.account_manager_workers:celery_app worker \
  --loglevel=info \
  --queues=account_manager_high,account_manager_normal,account_manager_low \
  --concurrency=2

# Beat scheduler для периодических задач
python -m celery -A app.workers.account_manager_workers:celery_app beat \
  --loglevel=info
```

## Интеграция с сервисами

### Invite Service

```python
# Пример использования в Invite Service
import httpx

class AccountManagerClient:
    def __init__(self):
        self.base_url = "http://integration-service:8000/api/v1/account-manager"
    
    async def allocate_account(self, user_id: int, purpose: str = "invite_campaign"):
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}/allocate", json={
                "user_id": user_id,
                "purpose": purpose,
                "service_name": "invite-service"
            })
            return response.json()
    
    async def release_account(self, account_id: str, usage_stats: dict):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/release/{account_id}", 
                json={
                    "service_name": "invite-service",
                    "usage_stats": usage_stats
                }
            )
            return response.json()
```

### Parsing Service

```python
# Пример для Parsing Service
async def get_parsing_account(user_id: int):
    allocation = await account_manager_client.allocate_account(
        user_id=user_id,
        purpose="parsing"
    )
    return allocation

async def release_parsing_account(account_id: str, success: bool = True):
    usage_stats = {
        "invites_sent": 0,
        "messages_sent": 0,
        "contacts_added": 0,
        "success": success
    }
    await account_manager_client.release_account(account_id, usage_stats)
```

## Лимиты и ограничения

### Telegram API Limits

| Действие | Дневной лимит | Часовой лимит | Per-channel | Cooldown |
|----------|---------------|---------------|-------------|----------|
| Приглашения | 30 | 5 | 15 | 2 минуты |
| Сообщения | 30 | 10 | - | 1 минута |
| Добавление контактов | 15 | 3 | - | 5 минут |

### Burst Limits

- **Приглашения**: максимум 3 подряд, затем 5 минут cooldown
- **Сообщения**: максимум 5 подряд, затем 3 минуты cooldown
- **Контакты**: максимум 2 подряд, затем 10 минут cooldown

## Обработка ошибок

### Типы ошибок

1. **FloodWaitError**: Временная блокировка на N секунд
   - Статус → `flood_wait`
   - Автоматическое восстановление через указанное время

2. **PeerFloodError**: Блокировка на 24 часа
   - Статус → `blocked`
   - Восстановление через 24 часа

3. **PhoneNumberBanned**: Постоянная блокировка
   - Статус → `disabled`
   - Требует ручного вмешательства

4. **AuthKeyError**: Проблемы с авторизацией
   - Статус → `disabled`
   - Требует переавторизации

### Стратегии восстановления

- **Автоматическое**: планирование восстановления по времени
- **Мониторинг**: проверка состояния и планирование
- **Ручное**: принудительное восстановление через API

## Мониторинг и алерты

### Health Check Integration

Account Manager интегрирован в `/api/v1/health/detailed`:

```json
{
  "components": {
    "account_manager": {
      "status": "healthy",
      "stats": {
        "total_accounts": 50,
        "healthy_accounts": 42,
        "health_percentage": 84.0,
        "flood_wait_active": 3,
        "blocked_active": 1,
        "recovery_queue_size": 2
      }
    }
  }
}
```

### Prometheus Метрики

- `account_manager_total_accounts` - Общее количество аккаунтов
- `account_manager_healthy_accounts` - Здоровые аккаунты
- `account_manager_flood_wait_active` - Аккаунты в flood wait
- `account_manager_blocked_active` - Заблокированные аккаунты
- `account_manager_allocations_total` - Счетчик выделений
- `account_manager_errors_total` - Счетчик ошибок

## Миграция и развертывание

### Применение миграций

```bash
cd backend/integration-service
alembic upgrade head
```

### Docker Compose (рекомендуется добавить)

```yaml
# Добавить в docker-compose.yml
account-manager-worker:
  build: ./backend/integration-service
  command: /app/start_account_manager_workers.sh
  environment:
    - POSTGRES_SERVER=integration-postgres
    - POSTGRES_USER=integration_user
    - POSTGRES_PASSWORD=integration_password
    - POSTGRES_DB=integration_db
    - REDIS_HOST=redis
    - REDIS_PORT=6379
    - LOG_LEVEL=INFO
  depends_on:
    - integration-postgres
    - redis
    - rabbitmq

account-manager-beat:
  build: ./backend/integration-service
  command: /app/start_account_manager_beat.sh
  environment:
    - POSTGRES_SERVER=integration-postgres
    - REDIS_HOST=redis
    - REDIS_PORT=6379
    - LOG_LEVEL=INFO
  depends_on:
    - integration-postgres
    - redis
```

## Безопасность

### Distributed Locking

- Redis-based блокировки с TTL
- Автоматическое освобождение при истечении времени
- Проверка владельца при освобождении

### Data Isolation

- Все операции изолированы по `user_id`
- Аккаунты пользователя доступны только ему
- Логирование всех действий с указанием пользователя

### Error Handling

- Graceful обработка всех исключений
- Автоматическое освобождение ресурсов при ошибках
- Детальное логирование для аудита

## Производительность

### Оптимизации

- Индексы на ключевые поля поиска аккаунтов
- Кэширование rate limiting данных в Redis
- Batch обработка в background tasks
- Connection pooling для PostgreSQL

### Scalability

- Горизонтальное масштабирование workers
- Распределенная архитектура через Redis
- Независимые очереди для разных приоритетов

## Troubleshooting

### Частые проблемы

1. **Аккаунты не выделяются**
   - Проверить здоровье аккаунтов: `GET /account-manager/stats/recovery`
   - Проверить блокировки в Redis: `redis-cli keys "account_lock:*"`

2. **FloodWait не снимается**
   - Проверить recovery queue: `redis-cli zrange "account_recovery_queue" 0 -1`
   - Запустить принудительную обработку: `POST /account-manager/maintenance/process-recoveries`

3. **Высокое потребление Redis**
   - Запустить очистку: `POST /account-manager/maintenance/cleanup-rate-limits`
   - Проверить TTL ключей: `redis-cli keys "*" | xargs -I {} redis-cli ttl {}`

### Диагностические команды

```bash
# Проверить состояние Celery workers
celery -A app.workers.account_manager_workers:celery_app inspect active

# Мониторинг Redis
redis-cli --latency-history -i 1

# Проверить PostgreSQL подключения
psql -h integration-postgres -U integration_user -d integration_db -c "SELECT COUNT(*) FROM telegram_sessions WHERE locked = true;"
```

## Заключение

Account Manager обеспечивает enterprise-уровень управления Telegram аккаунтами с:

✅ **Полной автоматизацией** распределения и восстановления  
✅ **Строгим соблюдением лимитов** Telegram API  
✅ **Comprehensive мониторингом** и алертингом  
✅ **Production-ready архитектурой** с горизонтальным масштабированием  
✅ **Безопасностью** на уровне enterprise систем  

Система готова к коммерческой эксплуатации и масштабированию.