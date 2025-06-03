# Модуль интеграций (Integration Service)

## Общее описание
Микросервис для централизованного подключения и управления интеграциями с внешними платформами, начиная с Telegram. В будущем — поддержка Instagram, WhatsApp, Threads, YouTube, TikTok и Webhook-сайтов.

## Метрики успеха
- [ ] Время подключения аккаунта ≤ 5 сек
- [ ] Доступность API ≥ 99.9%
- [ ] Максимальная задержка отправки сообщения ≤ 1 сек

## Технологический стек
- Python 3.11+
- FastAPI
- PostgreSQL 15+ (с поддержкой JSONB, массивов, полнотекстового поиска)
- Redis 7.0+
- RabbitMQ 3.12+
- Telethon (с возможным переходом на TDLib)
- Prometheus + Grafana
- ELK Stack
- HashiCorp Vault
- React (фронтенд)

## Архитектура и интеграция

### Взаимодействие с другими сервисами
- [ ] Интеграция с API Gateway (проксирование запросов)
- [ ] Интеграция с User Service (авторизация)
- [ ] Интеграция с Vault (хранение секретов)
- [ ] Интеграция с ELK (логирование)
- [ ] Интеграция с Prometheus (метрики)

### Структура базы данных (PostgreSQL)
```sql
-- Расширения
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Таблица для хранения сессий Telegram
CREATE TABLE telegram_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id INT NOT NULL,
    phone VARCHAR(20) NOT NULL,
    session_data JSONB NOT NULL,
    metadata JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Индексы для telegram_sessions
CREATE INDEX idx_telegram_sessions_user_id ON telegram_sessions(user_id);
CREATE INDEX idx_telegram_sessions_phone ON telegram_sessions(phone);
CREATE INDEX idx_telegram_sessions_metadata ON telegram_sessions USING GIN (metadata);

-- Таблица для хранения ботов
CREATE TABLE telegram_bots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id INT NOT NULL,
    bot_token VARCHAR(100) NOT NULL,
    username VARCHAR(50) NOT NULL,
    settings JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Индексы для telegram_bots
CREATE INDEX idx_telegram_bots_user_id ON telegram_bots(user_id);
CREATE INDEX idx_telegram_bots_username ON telegram_bots(username);
CREATE INDEX idx_telegram_bots_settings ON telegram_bots USING GIN (settings);

-- Таблица для хранения каналов/групп
CREATE TABLE telegram_channels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id INT NOT NULL,
    channel_id BIGINT NOT NULL,
    title VARCHAR(255) NOT NULL,
    type VARCHAR(20) NOT NULL CHECK (type IN ('channel', 'group')),
    settings JSONB,
    members_count INT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Индексы для telegram_channels
CREATE INDEX idx_telegram_channels_user_id ON telegram_channels(user_id);
CREATE INDEX idx_telegram_channels_channel_id ON telegram_channels(channel_id);
CREATE INDEX idx_telegram_channels_settings ON telegram_channels USING GIN (settings);
CREATE INDEX idx_telegram_channels_title_trgm ON telegram_channels USING GIN (title gin_trgm_ops);

-- Таблица для логов интеграций
CREATE TABLE integration_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id INT NOT NULL,
    integration_type VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('success', 'error')),
    details JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Индексы для integration_logs
CREATE INDEX idx_integration_logs_user_id ON integration_logs(user_id);
CREATE INDEX idx_integration_logs_created_at ON integration_logs(created_at);
CREATE INDEX idx_integration_logs_details ON integration_logs USING GIN (details);

-- Функция для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Триггеры для автоматического обновления updated_at
CREATE TRIGGER update_telegram_sessions_updated_at
    BEFORE UPDATE ON telegram_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_telegram_bots_updated_at
    BEFORE UPDATE ON telegram_bots
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_telegram_channels_updated_at
    BEFORE UPDATE ON telegram_channels
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

## Чек-лист задач

### 1. Базовая инфраструктура
- [ ] Создать docker-compose конфигурацию
- [ ] Настроить PostgreSQL базу данных
- [ ] Настроить Redis для кэширования
- [ ] Настроить RabbitMQ для очередей
- [ ] Интегрировать с Vault для секретов
- [ ] Настроить логирование в ELK
- [ ] Настроить метрики в Prometheus

### 2. API и эндпоинты
- [ ] Реализовать базовые CRUD операции
- [ ] Настроить JWT авторизацию
- [ ] Реализовать rate limiting
- [ ] Добавить валидацию входных данных
- [ ] Настроить CORS
- [ ] Добавить OpenAPI документацию
- [ ] Реализовать health check эндпоинты

### 3. Telegram интеграция
- [ ] Реализовать подключение аккаунтов через QR
- [ ] Реализовать подключение через SMS
- [ ] Добавить поддержку 2FA
- [ ] Реализовать подключение ботов
- [ ] Реализовать подключение каналов/групп
- [ ] Добавить проверку прав доступа
- [ ] Реализовать отправку сообщений

### 4. Безопасность
- [ ] Настроить шифрование сессий через Vault
- [ ] Реализовать rotation ключей
- [ ] Настроить ACL для API
- [ ] Добавить подпись webhook-запросов
- [ ] Реализовать rate limiting
- [ ] Настроить мониторинг безопасности
- [ ] Добавить аудит действий

### 5. Мониторинг и логирование
- [ ] Настроить метрики в Prometheus
- [ ] Создать дашборды в Grafana
- [ ] Настроить алерты в Alertmanager
- [ ] Настроить логирование в ELK
- [ ] Добавить трейсинг запросов
- [ ] Настроить мониторинг очередей
- [ ] Добавить мониторинг состояния сессий

### 6. Фронтенд интеграция
- [ ] Создать компоненты для подключения аккаунтов
- [ ] Реализовать отображение статуса интеграций
- [ ] Добавить статистику и метрики
- [ ] Реализовать управление ботами
- [ ] Добавить управление каналами/группами
- [ ] Реализовать отображение ошибок
- [ ] Добавить систему уведомлений

### 7. Масштабирование
- [ ] Настроить Celery для фоновых задач
- [ ] Реализовать параллельную обработку
- [ ] Настроить health checks
- [ ] Добавить circuit breakers
- [ ] Реализовать retry механизмы
- [ ] Настроить балансировку нагрузки
- [ ] Подготовить к k8s деплою

### 8. Тестирование
- [ ] Написать unit тесты
- [ ] Добавить интеграционные тесты
- [ ] Настроить CI/CD
- [ ] Реализовать нагрузочное тестирование
- [ ] Добавить тесты безопасности
- [ ] Настроить автоматическое тестирование
- [ ] Добавить тесты отказоустойчивости

## API Endpoints

### Telegram Accounts
```
POST /api/integrations/telegram/connect
GET /api/integrations/telegram/accounts
GET /api/integrations/telegram/accounts/{id}
DELETE /api/integrations/telegram/accounts/{id}
POST /api/integrations/telegram/accounts/{id}/reconnect
```

### Telegram Bots
```
POST /api/integrations/telegram/bots
GET /api/integrations/telegram/bots
GET /api/integrations/telegram/bots/{id}
DELETE /api/integrations/telegram/bots/{id}
POST /api/integrations/telegram/bots/{id}/send
```

### Telegram Channels
```
POST /api/integrations/telegram/channels
GET /api/integrations/telegram/channels
GET /api/integrations/telegram/channels/{id}
DELETE /api/integrations/telegram/channels/{id}
POST /api/integrations/telegram/channels/{id}/send
```

## Метрики Prometheus

```yaml
# Telegram Sessions
telegram_sessions_total{type="account"}
telegram_sessions_active{type="account"}
telegram_sessions_error{type="account"}

# Messages
telegram_messages_sent_total{type="account|bot|channel"}
telegram_messages_error_total{type="account|bot|channel"}

# API
api_request_duration_seconds{endpoint="/api/integrations/telegram/*"}
api_request_total{endpoint="/api/integrations/telegram/*"}
api_request_error_total{endpoint="/api/integrations/telegram/*"}

# Queue
celery_tasks_total{queue="high|mid|low"}
celery_tasks_error_total{queue="high|mid|low"}
```

## Алерты Alertmanager

```yaml
groups:
- name: telegram_integrations
  rules:
  - alert: TelegramSessionDown
    expr: telegram_sessions_active{type="account"} == 0
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "Telegram session is down"
      description: "Session {{ $labels.session_id }} is not active"

  - alert: HighErrorRate
    expr: rate(telegram_messages_error_total[5m]) > 0.1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High error rate in Telegram messages"
      description: "Error rate is {{ $value }}"
```

## Интеграция с Vault

```python
# Пример использования Vault для хранения сессий
def encrypt_session(session_data: bytes) -> bytes:
    client = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN)
    response = client.secrets.transit.encrypt_data(
        mount_point='transit',
        name='telegram-sessions',
        plaintext=base64.b64encode(session_data).decode()
    )
    return base64.b64decode(response['data']['ciphertext'])

def decrypt_session(encrypted_data: bytes) -> bytes:
    client = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN)
    response = client.secrets.transit.decrypt_data(
        mount_point='transit',
        name='telegram-sessions',
        ciphertext=base64.b64encode(encrypted_data).decode()
    )
    return base64.b64decode(response['data']['plaintext'])
```

## Следующие шаги
1. Создать базовую структуру проекта
2. Настроить инфраструктуру (PostgreSQL, Redis, RabbitMQ)
3. Реализовать базовые API эндпоинты
4. Интегрировать с существующими сервисами
5. Реализовать подключение Telegram аккаунтов
6. Добавить фронтенд компоненты
7. Настроить мониторинг и алерты 