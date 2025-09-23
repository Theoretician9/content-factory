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

#### Централизация в Account Manager
- Все лимиты и паузы применяются исключительно в Account Manager (AM).
- Invite Service не высчитывает скорость, не выставляет паузы и не ведет собственные счетчики.
- Перед каждым действием вызывается `AccountManagerClient.check_rate_limit()` с `action_type="invite"` и `target_channel_id`.

#### Фактические лимиты (реализованы в AM)
- 15 инвайтов в день на один конкретный паблик.
- 30 инвайтов в день на весь аккаунт.
- 200 инвайтов на паблик НАВСЕГДА (после достижения — аккаунт больше не может приглашать в этот паблик, но может в другие).
- Пауза между инвайтами: 10–15 минут. Равномерное распределение в течение дня.

#### Обработка Flood/PeerFlood
- FloodWait/PeerFlood/прочие Telegram-ограничения полностью обрабатываются в AM.
- Invite Service сообщает об ошибках вызовом `AccountManagerClient.handle_error()` и не реализует локальные cooldown.

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
    id SERIAL PRIMARY KEY,  -- Изменено с UUID на SERIAL для простоты
    user_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    platform VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    priority INTEGER NOT NULL,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Целевые пользователи для рассылки
CREATE TABLE invite_targets (
    id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES invite_tasks(id) ON DELETE CASCADE,
    username VARCHAR(255),
    phone_number VARCHAR(20),
    user_data JSONB DEFAULT '{}',
    status VARCHAR(20) NOT NULL,
    result JSONB DEFAULT '{}',
    processed_at TIMESTAMP,
    error_message TEXT
);

-- Аккаунты задействованные в задаче
CREATE TABLE invite_task_accounts (
    id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES invite_tasks(id) ON DELETE CASCADE,
    account_id VARCHAR(255) NOT NULL,
    platform VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    cooldown_until TIMESTAMP,
    stats JSONB DEFAULT '{}',
    last_used_at TIMESTAMP
);

-- Логи выполнения
CREATE TABLE invite_execution_logs (
    id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES invite_tasks(id) ON DELETE CASCADE,
    target_id INTEGER REFERENCES invite_targets(id) ON DELETE CASCADE,
    account_id VARCHAR(255) NOT NULL,
    action VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
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

Примечание: Модели и схемы Invite Service не содержат полей локальных лимитов или задержек.

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

## Последовательность вызовов и логирование

### Последовательность для одного приглашения
1. `allocate_account(user_id, purpose="invite_campaign")` — выделение аккаунта в AM.
2. `check_rate_limit(account_id, action_type="invite", target_channel_id)` — проверка лимитов и пауз.
3. Отправка приглашения через Integration Service (проксируется AM-политиками).
4. `release_account(account_id, usage_stats)` — освобождение аккаунта с учетом статистики.
5. При ошибках: `handle_error(account_id, error_type, error_message, context)`.

### Ключевые логи Invite Service
- "Account Manager: allocate_account..."
- "Account Manager: check_rate_limit..."
- "Account Manager: release_account..."
- "Account Manager: handle_error..."

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

---

## ОБНОВЛЕНИЯ И ИЗМЕНЕНИЯ В РЕАЛИЗАЦИИ

### 2025-08-22: Критические исправления базы данных и типов данных

#### **Исправления PostgreSQL enum типов**
В процессе реализации были внесены критические изменения в схему базы данных:

```sql
-- Созданные enum типы в PostgreSQL
CREATE TYPE taskstatus AS ENUM ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED', 'PAUSED');
CREATE TYPE taskpriority AS ENUM ('LOW', 'MEDIUM', 'HIGH');
CREATE TYPE targetsource AS ENUM ('MANUAL', 'FILE_UPLOAD', 'PARSING_IMPORT');
CREATE TYPE executionstatus AS ENUM ('PENDING', 'SUCCESS', 'FAILED', 'SKIPPED');

-- Обновление таблиц с enum типами
ALTER TABLE invite_tasks ALTER COLUMN status TYPE taskstatus USING status::taskstatus;
ALTER TABLE invite_tasks ALTER COLUMN priority TYPE taskpriority USING priority::taskpriority;
ALTER TABLE invite_targets ALTER COLUMN source TYPE targetsource USING source::targetsource;
ALTER TABLE invite_execution_logs ALTER COLUMN status TYPE executionstatus USING status::executionstatus;
```

#### **Обновленная схема базы данных**
```sql
-- Обновленная таблица invite_tasks
CREATE TABLE invite_tasks (
    id SERIAL PRIMARY KEY,  -- Изменено с UUID на SERIAL для простоты
    user_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    platform VARCHAR(50) NOT NULL,
    status taskstatus DEFAULT 'PENDING',
    priority taskpriority DEFAULT 'MEDIUM',
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Обновленная таблица invite_targets
CREATE TABLE invite_targets (
    id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES invite_tasks(id) ON DELETE CASCADE,
    username VARCHAR(255),
    phone_number VARCHAR(20),
    user_id_platform VARCHAR(255),
    email VARCHAR(255),
    full_name VARCHAR(255),
    source targetsource DEFAULT 'MANUAL',
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Обновленная таблица invite_execution_logs
CREATE TABLE invite_execution_logs (
    id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES invite_tasks(id) ON DELETE CASCADE,
    target_id INTEGER REFERENCES invite_targets(id) ON DELETE CASCADE,
    account_id VARCHAR(255) NOT NULL,
    action VARCHAR(100) NOT NULL,
    status executionstatus NOT NULL,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### **Исправления SQLAlchemy моделей**
```python
# backend/invite-service/app/models/invite_task.py
from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, JSON
from sqlalchemy.ext.declarative import declarative_base
from enum import Enum
from datetime import datetime

Base = declarative_base()

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"

class TaskPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class InviteTask(Base):
    __tablename__ = "invite_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    platform = Column(String(50), nullable=False)
    status = Column(SQLEnum(TaskStatus, name="taskstatus"), default=TaskStatus.PENDING)
    priority = Column(SQLEnum(TaskPriority, name="taskpriority"), default=TaskPriority.MEDIUM)
    settings = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

#### **Исправления Pydantic схем с валидаторами**
```python
# backend/invite-service/app/schemas/invite_task.py
from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime

class InviteTaskCreate(BaseModel):
    name: str
    platform: str
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    settings: Optional[dict] = {}
    
    @validator('status', pre=True)
    def validate_status(cls, v):
        if isinstance(v, str):
            return TaskStatus(v.upper())
        return v
    
    @validator('priority', pre=True)
    def validate_priority(cls, v):
        if isinstance(v, str):
            return TaskPriority(v.upper())
        return v

class InviteTaskResponse(BaseModel):
    id: int
    user_id: int
    name: str
    platform: str
    status: TaskStatus
    priority: TaskPriority
    settings: dict
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True
```

#### **Межсервисная интеграция с Integration Service**

**Исправления типов данных account_id:**
```python
# Все идентификаторы аккаунтов приведены к UUID формату
# backend/integration-service/app/schemas/telegram_invites.py
from uuid import UUID

class TelegramAccountLimitsResponse(BaseModel):
    account_id: UUID  # Исправлено с int на UUID
    limits: Dict[str, int]
    current_usage: Dict[str, int]
    restrictions: List[str]
    last_updated: datetime
```

**Исправления JWT аутентификации:**
```python
# backend/invite-service/app/services/integration_client.py
async def _get_jwt_token(self) -> str:
    """JWT токен для межсервисной аутентификации"""
    payload = {
        'sub': 'nikita.f3d@gmail.com',  # Поле sub с email пользователя
        'service': 'invite-service',
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, secret_data['secret_key'], algorithm='HS256')
```

#### **Обновленные API endpoints Integration Service**
```python
# backend/integration-service/app/api/v1/endpoints/telegram_invites.py
@router.get("/accounts/{account_id}/limits", response_model=TelegramAccountLimitsResponse)
async def get_account_limits(account_id: UUID, request: Request):
    """Получение лимитов Telegram аккаунта"""
    user_id = await get_user_id_from_request(request)
    account = await telegram_service.session_service.get_user_session_by_id(session, user_id, account_id)
    
    if not account:
        raise HTTPException(status_code=404, detail="Telegram аккаунт не найден")
    
    limits = {
        "daily_invites": 50,
        "daily_messages": 40,
        "hourly_invites": 5,
        "flood_wait_buffer": 300
    }
    
    current_usage = {
        "daily_invites_used": 0,
        "daily_messages_used": 0,
        "hourly_invites_used": 0
    }
    
    return TelegramAccountLimitsResponse(
        account_id=account_id,
        limits=limits,
        current_usage=current_usage,
        restrictions=[],
        last_updated=datetime.utcnow()
    )
```

### Текущий статус реализации

#### **✅ Полностью работает (через Account Manager):**
- Invite Service использует Account Manager для выделения/освобождения аккаунтов, проверки лимитов и обработки ошибок.
- Локальные лимиты и паузы удалены; batch_size = 1 для соблюдения ТЗ.
- Логи подтверждают последовательность allocate → check_rate_limit → send → release.

#### **🧪 Рекомендуемые проверки:**
1. Пауза 10–15 минут между инвайтами в один паблик (AM возвращает `wait_for_seconds`).
2. 15/день на паблик — 16‑й инвайт должен быть заблокирован AM.
3. 30/день на аккаунт — 31‑й инвайт должен быть заблокирован AM.
4. 200 lifetime на паблик — 201‑й инвайт в тот же паблик должен быть навсегда отклонен.

#### **📊 Архитектурные достижения:**
- Централизация лимитов и управления аккаунтами в AM.
- Единый источник правды по паузам и лимитам.
- Устойчивость к Flood/PeerFlood за счет AM recovery.