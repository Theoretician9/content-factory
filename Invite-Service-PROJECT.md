# INVITE SERVICE - ТЕХНИЧЕСКОЕ ЗАДАНИЕ ДЛЯ РАЗРАБОТКИ

> **Это подробное техническое задание для создания микросервиса Invite Service в рамках существующей SaaS-платформы content-factory. Документ написан для разработчика и содержит все необходимые детали для реализации сервиса массовых рассылок и приглашений пользователей в мессенджеры.**

## КОНТЕКСТ ПРОЕКТА

### Существующая архитектура
- **Микросервисная SaaS-платформа** для автоматизации маркетинга и генерации контента
- **Docker Compose** инфраструктура с единой backend сетью
- **Технологический стек**: Python (FastAPI), PostgreSQL, MySQL, Redis, RabbitMQ, Vault, Nginx, ELK, Prometheus/Grafana
- **Уже реализованы и работают**:
  - **Integration Service** - управление подключенными аккаунтами (Telegram с QR/SMS/2FA)
  - **Parsing Service** - сбор аудитории из мессенджеров (мультиплатформенный)
  - **API Gateway** - единая точка входа с JWT авторизацией
  - **User Service** - управление пользователями
- **Безопасность**: Vault с AppRole Authentication, HTTPS, изоляция данных по user_id

### Место Invite Service в архитектуре
Invite Service является **третьим ключевым микросервисом** воронки:
1. **Integration Service** → подключение аккаунтов мессенджеров
2. **Parsing Service** → сбор целевой аудитории 
3. **Invite Service** → массовые рассылки и приглашения (новый сервис)

## ЦЕЛИ И НАЗНАЧЕНИЕ

### Основная цель
Реализовать **безопасный и эффективный** микросервис для автоматизированной отправки приглашений в группы/каналы и личных сообщений в мессенджерах с использованием подключенных аккаунтов пользователей.

### Ключевые принципы
- **Соблюдение лимитов платформ** - строгое следование антиспам ограничениям
- **Мультиаккаунтность** - распределение нагрузки между аккаунтами пользователя
- **Адаптивность** - динамическое управление скоростью при флуд-ограничениях
- **Прозрачность** - детальная статистика и отчетность в реальном времени
- **Расширяемость** - архитектура для будущего добавления Instagram/WhatsApp

## АРХИТЕКТУРА И ТЕХНИЧЕСКИЕ ТРЕБОВАНИЯ

### Микросервисная архитектура
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Integration    │────│   Invite         │────│   Parsing       │
│  Service        │    │   Service        │    │   Service       │
│  (аккаунты)     │    │   (рассылки)     │    │   (аудитория)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌──────────────────┐
                    │   API Gateway    │
                    │  (JWT Auth)      │
                    └──────────────────┘
```

### Технологический стек
- **Backend**: Python 3.11+, FastAPI (аналогично другим сервисам)
- **База данных**: PostgreSQL 15 (отдельная БД invite_service)
- **Очереди**: Celery + RabbitMQ (для фоновой обработки)
- **Кэширование**: Redis (состояния задач, аккаунтов)
- **Безопасность**: Vault AppRole Authentication
- **Мониторинг**: Prometheus метрики, логирование в ELK
- **Platform API Libraries**: 
  - Telegram: Telethon/Pyrogram
  - Instagram: instagram-private-api (для будущего)
  - WhatsApp: whatsapp-web.js или Cloud API (для будущего)

### Структура проекта
```
backend/invite-service/
├── app/
│   ├── api/v1/endpoints/           # REST API endpoints
│   ├── core/                      # Конфигурация, аутентификация
│   ├── models/                    # SQLAlchemy модели
│   ├── schemas/                   # Pydantic схемы
│   ├── services/                  # Бизнес-логика
│   ├── adapters/                  # Platform adapters (Strategy pattern)
│   ├── workers/                   # Celery воркеры
│   └── utils/                     # Вспомогательные утилиты
├── migrations/                    # Alembic миграции
├── requirements.txt
├── Dockerfile
└── main.py
```

## ФУНКЦИОНАЛЬНЫЕ ТРЕБОВАНИЯ

### Основной функционал

#### 1. Управление задачами рассылок
- **Создание задач** через REST API с параметрами:
  - Платформа (telegram, instagram, whatsapp)
  - Источник аудитории (parsing-service ID или загруженный файл)
  - Тип действия (приглашение в группу/канал, личные сообщения)
  - Текст сообщения с поддержкой переменных {username}, {first_name}
  - Приоритет задачи (HIGH, NORMAL, LOW)
  - Расписание (немедленно или отложенный запуск)

#### 2. Импорт целевой аудитории
**Источники данных:**
- **Parsing Service API**: `GET /api/parsing/results/{task_id}/users`
- **Загрузка файлов**: CSV, XLSX, JSON с автоматическим определением столбцов
- **Валидация данных**: проверка форматов username, phone, user_id

**Поддерживаемые форматы идентификаторов:**
- Telegram: @username, user_id, +phone
- Instagram: username, user_id (для будущего)
- WhatsApp: +phone в международном формате (для будущего)

#### 3. Управление аккаунтами
**Интеграция с Integration Service:**
- `GET /api/integrations/accounts?platform=telegram&user_id={user_id}`
- Получение активных аккаунтов с проверкой статуса
- Автоматическое исключение заблокированных аккаунтов
- Кэширование данных аккаунтов в Redis

#### 4. Platform Adapters (Strategy Pattern)
**Абстрактный интерфейс:**
```python
class InviteStrategy(ABC):
    @abstractmethod
    async def initialize_client(self, account_data: dict) -> bool
    
    @abstractmethod
    async def invite_to_group(self, target_user: str, group_id: str) -> InviteResult
    
    @abstractmethod
    async def send_message(self, target_user: str, message: str) -> MessageResult
    
    @abstractmethod
    async def add_to_contacts(self, target_user: str) -> bool
    
    @abstractmethod
    def get_rate_limits(self) -> RateLimitConfig
```

**TelegramStrategy (первоочередная реализация):**
- Инициализация TelegramClient через Telethon
- Обработка session данных из Vault
- Проверка прав администратора в целевых группах/каналах
- Автоматическое добавление в контакты при необходимости
- Graceful обработка FloodWait, PrivacyRestriction, PeerFlood

### Система управления скоростью и лимитами

#### Автоматическое определение скорости
**Алгоритм расчета:**
```python
def calculate_optimal_speed(
    platform: Platform,
    accounts_count: int,
    target_users_count: int,
    message_has_links: bool
) -> RateConfig:
    # Telegram лимиты
    if platform == Platform.TELEGRAM:
        daily_limit_per_account = 10 if message_has_links else 40
        pause_between_actions = 15  # секунд
        
        total_daily_capacity = accounts_count * daily_limit_per_account
        estimated_hours = max(1, target_users_count / total_daily_capacity * 24)
        
        return RateConfig(
            messages_per_hour=total_daily_capacity // 24,
            pause_between_messages=pause_between_actions,
            accounts_rotation=True
        )
```

#### Система антифлуд защиты
**FloodWait обработка:**
- Автоматическое обнаружение FloodWaitError
- Постановка аккаунта на cooldown согласно серверному времени ожидания
- Перераспределение нагрузки на активные аккаунты
- Автоматическое возобновление после cooldown

**Адаптивное замедление:**
- Мониторинг частоты FloodWait событий
- Динамическое увеличение пауз между действиями
- Снижение параллелизма при превышении порогов

#### Приоритизация задач
**Celery очереди:**
- `invite-high-priority` - срочные задачи
- `invite-normal` - обычные задачи  
- `invite-low` - фоновые задачи

**Распределение ресурсов:**
- High priority задачи получают больше аккаунтов
- Round-robin между задачами одного приоритета
- Преemption: возможность приостановить низкоприоритетные задачи

## БАЗА ДАННЫХ И МОДЕЛИ

### Схема PostgreSQL
```sql
-- Основная таблица задач
CREATE TABLE invite_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    platform VARCHAR(20) NOT NULL,
    task_type VARCHAR(20) NOT NULL, -- 'invite_to_group', 'send_messages'
    title VARCHAR(255) NOT NULL,
    description TEXT,
    target_group_id VARCHAR(255), -- для приглашений в группу
    message_template TEXT,
    priority INTEGER DEFAULT 2, -- 1=HIGH, 2=NORMAL, 3=LOW
    status VARCHAR(20) DEFAULT 'pending',
    progress JSONB DEFAULT '{}',
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    scheduled_at TIMESTAMP WITH TIME ZONE,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Целевые пользователи для рассылки
CREATE TABLE invite_targets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES invite_tasks(id) ON DELETE CASCADE,
    user_identifier VARCHAR(255) NOT NULL,
    user_data JSONB DEFAULT '{}', -- {username, first_name, phone, etc}
    status VARCHAR(20) DEFAULT 'pending',
    result JSONB DEFAULT '{}',
    processed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT
);

-- Аккаунты задействованные в задаче
CREATE TABLE invite_task_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES invite_tasks(id) ON DELETE CASCADE,
    account_id VARCHAR(255) NOT NULL,
    platform VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'active', -- active, cooldown, blocked
    cooldown_until TIMESTAMP WITH TIME ZONE,
    stats JSONB DEFAULT '{}',
    last_used_at TIMESTAMP WITH TIME ZONE
);

-- Логи выполнения
CREATE TABLE invite_execution_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES invite_tasks(id) ON DELETE CASCADE,
    target_id UUID REFERENCES invite_targets(id) ON DELETE CASCADE,
    account_id VARCHAR(255) NOT NULL,
    action VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Индексы для производительности
CREATE INDEX idx_invite_tasks_user_status ON invite_tasks(user_id, status);
CREATE INDEX idx_invite_targets_task_status ON invite_targets(task_id, status);
CREATE INDEX idx_invite_logs_task_created ON invite_execution_logs(task_id, created_at);
```

### SQLAlchemy модели
**Основные модели:**
- `InviteTask` - основная модель задачи
- `InviteTarget` - целевые пользователи
- `InviteTaskAccount` - аккаунты в задаче
- `InviteExecutionLog` - логи выполнения

**Pydantic схемы:**
- `InviteTaskCreate`, `InviteTaskResponse`
- `TargetUserImport`, `TaskStatusResponse`
- `TaskStatistics`, `AccountStatus`

## API ENDPOINTS

### Основные endpoints
```python
# Управление задачами
POST   /api/v1/invite/tasks                    # Создание задачи
GET    /api/v1/invite/tasks                    # Список задач пользователя
GET    /api/v1/invite/tasks/{task_id}          # Детали задачи
PUT    /api/v1/invite/tasks/{task_id}          # Обновление задачи
DELETE /api/v1/invite/tasks/{task_id}          # Удаление задачи

# Управление выполнением
POST   /api/v1/invite/tasks/{task_id}/start    # Запуск задачи
POST   /api/v1/invite/tasks/{task_id}/pause    # Пауза
POST   /api/v1/invite/tasks/{task_id}/resume   # Возобновление
POST   /api/v1/invite/tasks/{task_id}/cancel   # Отмена

# Статистика и отчеты
GET    /api/v1/invite/tasks/{task_id}/status   # Статус выполнения
GET    /api/v1/invite/tasks/{task_id}/stats    # Детальная статистика
GET    /api/v1/invite/tasks/{task_id}/report   # Финальный отчет
GET    /api/v1/invite/tasks/{task_id}/logs     # Логи выполнения

# Импорт аудитории
POST   /api/v1/invite/import/file              # Загрузка файла
POST   /api/v1/invite/import/parsing           # Из parsing-service
GET    /api/v1/invite/import/validate          # Валидация данных

# Служебные endpoints
GET    /api/v1/invite/health                   # Health check
GET    /api/v1/invite/accounts                 # Доступные аккаунты
```

## CELERY ВОРКЕРЫ И ФОНОВЫЕ ЗАДАЧИ

### Архитектура воркеров
```python
# Основные Celery задачи
@celery_app.task(bind=True)
def execute_invite_task(self, task_id: str):
    """Главная задача выполнения рассылки"""
    
@celery_app.task
def process_target_batch(task_id: str, target_ids: List[str], account_id: str):
    """Обработка батча пользователей одним аккаунтом"""
    
@celery_app.task
def reactivate_account_after_cooldown(account_id: str, task_id: str):
    """Возобновление аккаунта после FloodWait"""
    
@celery_app.task
def cleanup_completed_tasks():
    """Очистка старых завершенных задач"""
```

### Стратегия выполнения
**Параллелизация по аккаунтам:**
- Каждый аккаунт получает свой батч пользователей
- Независимые Celery подзадачи для каждого аккаунта
- Координация через Redis для синхронизации статуса

**Обработка ошибок:**
- Retry механизм для временных ошибок сети
- Permanent fail для заблокированных аккаунтов
- Circuit breaker для массовых ошибок API

## БЕЗОПАСНОСТЬ И ИНТЕГРАЦИИ

### Vault Integration
**AppRole Authentication:**
```python
# Конфигурация аналогично другим сервисам
VAULT_ADDR=http://vault:8201
VAULT_ROLE_ID=${INVITE_SERVICE_ROLE_ID}
VAULT_SECRET_ID=${INVITE_SERVICE_SECRET_ID}

# Секреты в Vault
secret/invite-service/jwt_secret
secret/telegram/api_credentials
```

### Авторизация и изоляция
- **JWT токены** - валидация через общий secret из Vault
- **User isolation** - все данные фильтруются по user_id из токена
- **Account access** - доступ только к аккаунтам текущего пользователя
- **Audit logging** - все действия пользователей логируются

### Integration Service API
**Получение аккаунтов:**
```python
async def get_user_accounts(user_id: str, platform: str) -> List[AccountData]:
    response = await http_client.get(
        f"{INTEGRATION_SERVICE_URL}/api/v1/accounts",
        params={"user_id": user_id, "platform": platform, "status": "active"}
    )
    return response.json()
```

## МОНИТОРИНГ И МЕТРИКИ

### Prometheus метрики
```python
# Основные метрики
invite_tasks_total = Counter('invite_tasks_total', ['platform', 'status'])
invite_targets_processed = Counter('invite_targets_processed', ['platform', 'result'])
invite_accounts_blocked = Counter('invite_accounts_blocked', ['platform'])
invite_floodwait_events = Counter('invite_floodwait_events', ['platform'])
invite_task_duration = Histogram('invite_task_duration_seconds', ['platform'])
invite_active_tasks = Gauge('invite_active_tasks', ['platform'])
```

### Логирование
**Структурированные логи:**
```python
logger.info(
    "Task started",
    extra={
        "task_id": task_id,
        "user_id": user_id,
        "platform": platform,
        "targets_count": len(targets),
        "accounts_count": len(accounts)
    }
)
```

### Alerting правила
- Высокий процент заблокированных аккаунтов
- Длительно висящие задачи
- Ошибки интеграции с внешними сервисами
- Превышение лимитов очереди Celery

## ТЕСТИРОВАНИЕ И РАЗВЕРТЫВАНИЕ

### Docker конфигурация
```yaml
# docker-compose.yml дополнение
invite-service:
  build: ./backend/invite-service
  environment:
    - DATABASE_URL=postgresql://invite_user:invite_password@invite-postgres:5432/invite_db
    - REDIS_URL=redis://redis:6379/3
    - CELERY_BROKER_URL=amqp://user:password@rabbitmq:5672//
    - VAULT_ADDR=http://vault:8201
    - VAULT_ROLE_ID=${INVITE_SERVICE_ROLE_ID}
    - VAULT_SECRET_ID=${INVITE_SERVICE_SECRET_ID}
  ports:
    - "127.0.0.1:8003:8000"
  networks:
    - backend
```

### Тестовая стратегия
- **Unit тесты** - Platform adapters, бизнес-логика
- **Integration тесты** - API endpoints, database операции  
- **E2E тесты** - полный workflow с mock Telegram API
- **Load тесты** - производительность при массовых рассылках

### Поэтапное развертывание
1. **Фаза 1**: Базовая архитектура, Telegram adapter
2. **Фаза 2**: Полная функциональность, статистика, мониторинг
3. **Фаза 3**: Оптимизация производительности
4. **Фаза 4**: Instagram/WhatsApp adapters (будущее)

## ПРОИЗВОДИТЕЛЬНОСТЬ И МАСШТАБИРОВАНИЕ

### Оптимизация
- **Connection pooling** для PostgreSQL и Redis
- **Батчинг** операций в БД (bulk insert/update)
- **Кэширование** статусов аккаунтов и задач в Redis
- **Async I/O** для всех внешних API вызовов

### Горизонтальное масштабирование
- **Multiple Celery workers** для обработки задач
- **Database sharding** по user_id при росте нагрузки
- **Redis cluster** для кэширования
- **Load balancer** для FastAPI инстансов

### Лимиты и ограничения
- Максимум 1000 целевых пользователей на задачу (изначально)
- Максимум 10 одновременных задач на пользователя
- Размер загружаемого файла до 10MB
- Retention политика для логов - 30 дней

---

**Этот документ является исчерпывающим техническим заданием для реализации Invite Service в рамках существующей архитектуры content-factory проекта. При разработке необходимо строго следовать описанным принципам и интегрироваться с существующими сервисами.** 