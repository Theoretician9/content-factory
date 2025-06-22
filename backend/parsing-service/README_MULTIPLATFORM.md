# Multi-Platform Parser Service

🚀 **Универсальный сервис парсинга для социальных платформ (Telegram, Instagram, WhatsApp и др.)**

## 📋 Содержание

- [Обзор](#обзор)
- [Архитектура](#архитектура)
- [Быстрый старт](#быстрый-старт)
- [API Documentation](#api-documentation)
- [Конфигурация](#конфигурация)
- [Мониторинг](#мониторинг)
- [Разработка](#разработка)

## 🎯 Обзор

Multi-Platform Parser Service - это микросервис для универсального парсинга данных из различных социальных платформ с единообразным API и мультиплатформенной архитектурой.

### ✨ Основные возможности

- 🔌 **Мультиплатформенность**: Поддержка Telegram, Instagram, WhatsApp и других платформ
- ⚡ **Асинхронность**: Celery воркеры для параллельной обработки задач
- 🏗️ **Модульность**: Система адаптеров для легкого добавления новых платформ
- 🔐 **Безопасность**: Интеграция с Vault для управления секретами
- 📊 **Мониторинг**: Prometheus метрики и Grafana дашборды
- 🔄 **Масштабируемость**: Горизонтальное масштабирование воркеров

### 📱 Поддерживаемые платформы

| Платформа | Статус | Фаза | Возможности |
|-----------|--------|------|-------------|
| **Telegram** | ✅ Активна | Phase 1 | Каналы, группы, сообщения, медиа |
| **Instagram** | 🚧 Разработка | Phase 2 | Посты, истории, профили |
| **WhatsApp** | 📋 Планируется | Phase 3 | Группы, сообщения |
| **Facebook** | 📋 Планируется | Phase 4 | Посты, группы |

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway                              │
│                  (JWT Authentication)                       │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│              Parsing Service API                           │
│                (FastAPI + uvicorn)                         │
│  ┌─────────────┐ ┌──────────────┐ ┌─────────────────────┐   │
│  │   Legacy    │ │   New API    │ │     Monitoring      │   │
│  │ Endpoints   │ │   (v1/*)     │ │   (Prometheus)      │   │
│  └─────────────┘ └──────────────┘ └─────────────────────┘   │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                 Task Queues (RabbitMQ)                     │
│  ┌─────────────┐ ┌──────────────┐ ┌─────────────────────┐   │
│  │  telegram   │ │  instagram   │ │     whatsapp        │   │
│  │   queue     │ │    queue     │ │      queue          │   │
│  └─────────────┘ └──────────────┘ └─────────────────────┘   │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                Celery Workers                               │
│  ┌─────────────┐ ┌──────────────┐ ┌─────────────────────┐   │
│  │  Telegram   │ │  Instagram   │ │     WhatsApp        │   │
│  │  Adapter    │ │   Adapter    │ │     Adapter         │   │
│  └─────────────┘ └──────────────┘ └─────────────────────┘   │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────▼─────────────┐
        │                           │
        ▼                           ▼
┌─────────────────┐        ┌─────────────────┐
│   PostgreSQL    │        │     Vault       │
│   (Results)     │        │   (Secrets)     │
└─────────────────┘        └─────────────────┘
```

### 🔧 Компоненты

1. **API Layer**: FastAPI приложение с v1 API и legacy endpoints
2. **Platform Adapters**: Модульные адаптеры для каждой платформы
3. **Task Queue**: RabbitMQ с отдельными очередями по платформам
4. **Workers**: Celery воркеры для асинхронной обработки
5. **Database**: PostgreSQL для хранения задач и результатов
6. **Vault**: HashiCorp Vault для секретов и session файлов
7. **Monitoring**: Prometheus + Grafana для мониторинга

## 🚀 Быстрый старт

### 1️⃣ Подготовка

```bash
# Клонирование проекта
cd backend/parsing-service

# Проверка зависимостей
cat requirements.txt
```

### 2️⃣ Конфигурация

Создайте `.env` файл:

```bash
# Database
POSTGRES_HOST=parsing-postgres
POSTGRES_USER=parsing_user
POSTGRES_PASSWORD=parsing_password
POSTGRES_DATABASE=parsing_db

# Vault
VAULT_ADDR=http://vault:8201
VAULT_ROLE_ID=your_role_id
VAULT_SECRET_ID=your_secret_id

# JWT
JWT_SECRET_KEY=your_super_secret_jwt_key

# Integration Service
INTEGRATION_SERVICE_URL=http://integration-service:8000

# Настройки
DEBUG=true
LOG_LEVEL=INFO
PROMETHEUS_METRICS_ENABLED=true
```

### 3️⃣ Запуск (Docker)

```bash
# Запуск всех сервисов
docker-compose -f docker-compose.multiplatform.yml up -d

# Запуск только Phase 1 (Telegram)
docker-compose -f docker-compose.multiplatform.yml up -d parsing-postgres parsing-redis parsing-rabbitmq parsing-service parsing-worker-telegram

# Запуск с мониторингом
docker-compose -f docker-compose.multiplatform.yml --profile monitoring up -d

# Выполнение миграций
docker-compose -f docker-compose.multiplatform.yml --profile migrate up parsing-migrate
```

### 4️⃣ Проверка

```bash
# Проверка здоровья сервиса
curl http://localhost:8003/health

# Проверка API
curl http://localhost:8003/

# Prometheus метрики
curl http://localhost:8004/metrics

# RabbitMQ Management UI
open http://localhost:15673
# Логин: parsing_user / parsing_password

# Flower (Celery monitoring) 
open http://localhost:5556
```

## 📡 API Documentation

### 🔗 Endpoints

| Endpoint | Метод | Описание | Тип |
|----------|-------|----------|-----|
| `/health` | GET | Проверка состояния сервиса | New |
| `/v1/health/` | GET | Детальная проверка здоровья | New |
| `/v1/tasks/` | POST | Создать задачу парсинга | New |
| `/v1/tasks/` | GET | Список задач пользователя | New |
| `/v1/tasks/{id}` | GET | Получить задачу | New |
| `/v1/tasks/{id}/start` | POST | Запустить задачу | New |
| `/v1/results/` | GET | Результаты парсинга | New |
| `/parse` | POST | Универсальный парсинг | Legacy |
| `/stats` | GET | Статистика | Legacy |

### 📝 Примеры запросов

#### Создание Telegram задачи

```bash
curl -X POST "http://localhost:8003/v1/tasks/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "telegram",
    "task_type": "parse_group",
    "title": "Парсинг крипто каналов",
    "description": "Сбор сообщений из криптовалютных каналов",
    "config": {
      "targets": ["@cryptonews", "@bitcoinchannel"],
      "message_limit": 5000,
      "include_media": true,
      "date_from": "2024-01-01",
      "filters": {
        "keywords": ["bitcoin", "crypto", "blockchain"],
        "exclude_keywords": ["spam"]
      }
    },
    "priority": "high",
    "output_format": "json"
  }'
```

#### Получение результатов

```bash
curl -X GET "http://localhost:8003/v1/results/?task_id=123&platform=telegram" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## ⚙️ Конфигурация

### 🗄️ База данных

PostgreSQL используется как основная БД:

```yaml
# docker-compose.multiplatform.yml
parsing-postgres:
  image: postgres:15-alpine
  environment:
    POSTGRES_DB: parsing_db
    POSTGRES_USER: parsing_user
    POSTGRES_PASSWORD: parsing_password
```

### 🔐 Vault интеграция

Настройка секретов в Vault:

```bash
# Telegram API ключи
vault kv put integrations/telegram/api_keys \
  api_id="YOUR_API_ID" \
  api_hash="YOUR_API_HASH"

# Telegram session файлы
vault kv put integrations/telegram/sessions/session_1 \
  session_data="base64_encoded_session_file"
```

### 🏃 Celery Workers

Конфигурация воркеров по платформам:

```yaml
# Telegram worker
parsing-worker-telegram:
  command: celery -A app.workers.celery_app worker --queues=telegram --concurrency=2
  
# Instagram worker (Phase 2)
parsing-worker-instagram:
  command: celery -A app.workers.celery_app worker --queues=instagram --concurrency=1
  profiles: [phase2]
```

## 📊 Мониторинг

### 📈 Prometheus метрики

Доступны метрики по адресу `http://localhost:8004/metrics`:

- `parsing_tasks_total` - Общее количество задач
- `parsing_results_total` - Количество результатов
- `parsing_rate_limits_total` - Ограничения по скорости
- `telegram_flood_waits_total` - Telegram FloodWait ошибки
- `parsing_active_tasks` - Активные задачи

### 📊 Grafana Dashboard

Импортируйте готовый дашборд:

```json
{
  "dashboard": {
    "title": "Multi-Platform Parser Service",
    "panels": [
      {
        "title": "Tasks by Platform",
        "type": "stat",
        "targets": [
          {
            "expr": "sum by (platform) (parsing_tasks_total)"
          }
        ]
      },
      {
        "title": "Parsing Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(parsing_results_total[5m])"
          }
        ]
      }
    ]
  }
}
```

## 🛠️ Разработка

### 🏗️ Добавление новой платформы

1. **Создать адаптер**:
```python
# app/adapters/new_platform.py
from .base import BasePlatformAdapter

class NewPlatformAdapter(BasePlatformAdapter):
    async def authenticate(self, account_id, credentials):
        # Реализация аутентификации
        pass
    
    async def parse_target(self, task, target, config):
        # Реализация парсинга
        pass
```

2. **Добавить в конфигурацию**:
```python
# app/core/config.py
SUPPORTED_PLATFORMS = [
    Platform.TELEGRAM,
    Platform.NEW_PLATFORM  # Добавить новую платформу
]
```

3. **Создать воркер**:
```python
# app/workers/new_platform_worker.py
@celery_app.task(queue="new_platform")
def process_new_platform_task(task_id, config):
    # Обработка задач новой платформы
    pass
```

### 🧪 Тестирование

```bash
# Установка dev зависимостей
pip install pytest pytest-asyncio

# Запуск тестов
pytest tests/

# Тесты конкретного адаптера
pytest tests/test_telegram_adapter.py
```

### 📝 Логирование

Логи структурированы по уровням:

```python
import logging
logger = logging.getLogger(__name__)

# Информационные сообщения
logger.info("✅ Task completed successfully")

# Предупреждения
logger.warning("⚠️ Rate limit approaching")

# Ошибки
logger.error("❌ Authentication failed")
```

## 🔄 Migration от Legacy

### Поэтапная миграция

1. **Phase 1**: Запуск нового сервиса параллельно со старым
2. **Phase 2**: Переключение клиентов на новые endpoints
3. **Phase 3**: Отключение legacy endpoints

### Совместимость

- Legacy endpoints сохранены для обратной совместимости
- Новые API используют префикс `/v1/`
- Один и тот же Docker контейнер поддерживает оба API

## 🆘 Troubleshooting

### Частые проблемы

**1. База данных не подключается**
```bash
# Проверка подключения
docker-compose logs parsing-postgres
docker-compose exec parsing-service alembic current
```

**2. Vault недоступен**
```bash
# Проверка Vault
curl http://localhost:8201/v1/sys/health
```

**3. Celery воркеры не запускаются**
```bash
# Проверка RabbitMQ
docker-compose logs parsing-rabbitmq
docker-compose exec parsing-service celery -A app.workers.celery_app inspect active
```

**4. Telegram API ошибки**
```bash
# Проверка логов Telegram воркера
docker-compose logs parsing-worker-telegram
```

### Полезные команды

```bash
# Просмотр активных задач
docker-compose exec parsing-service celery -A app.workers.celery_app inspect active

# Очистка очереди
docker-compose exec parsing-service celery -A app.workers.celery_app purge

# Миграции БД
docker-compose exec parsing-service alembic upgrade head

# Просмотр метрик
curl http://localhost:8004/metrics | grep parsing_
```

## 📞 Поддержка

- 📧 **Email**: support@content-factory.xyz
- 📱 **Telegram**: @contentfactory_support
- 🐛 **Issues**: GitHub Issues
- 📚 **Docs**: `/docs` endpoint в DEBUG режиме

---

**🎯 Multi-Platform Parser Service v1.0.0**  
*Универсальный парсинг для всех социальных платформ* 