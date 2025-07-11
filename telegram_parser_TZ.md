# Техническое задание (ТЗ)

## Название проекта

**Telegram Parser Service** — микросервис сбора максимально полной информации из Telegram по ссылкам на группы и публичные каналы. Интегрируется в текущую архитектуру проекта `content-factory.xyz`.

---

## Цель

Создать масштабируемый, отказоустойчивый и безопасный микросервис Telegram-парсера, который позволяет пользователю:

- вводить ссылки на Telegram-группы и публичные каналы в очередь
- выполнять глубокий парсинг всех доступных данных
- распределять нагрузку между своими Telegram-аккаунтами
- использовать результаты в других микросервисах
- находить сообщества по теме

---

## Архитектура микросервиса

### Общие компоненты:

- **parser-api** — FastAPI-интерфейс взаимодействия с пользователем и другими сервисами
- **parser-worker** — Celery-воркеры для асинхронной и параллельной обработки задач
- **parser-db** — PostgreSQL база данных для хранения результатов и метаинформации
- **parser-state** — Redis-хранилище текущих статусов задач, FloodWait, статусов аккаунтов
- **proxy-adapter** — абстрактный слой подключения к будущему Proxy-сервису (не реализуется сейчас)

### Взаимодействие с текущими микросервисами:

- **Integration Service** предоставляет список Telegram-сессий пользователя, их статус (`is_banned`, `flood_wait_until`, `is_working` и пр.)
- **Vault Service** хранит `.session`-файлы в зашифрованном виде и выдаёт их по запросу
- **API Gateway** — через него проходят все внешние запросы пользователя

---

## Функциональность

### 1. Интерфейс добавления задач

- API-эндпоинт `POST /parser/queue`
- Поддержка множественного ввода ссылок на группы и каналы
- Поле `priority`: "low" | "normal" | "high"
- Пример запроса:

```json
{
  "links": ["https://t.me/example1", "https://t.me/example2"],
  "user_id": 15,
  "priority": "normal"
}
```

- Ссылки валидируются, проверяется доступность, формат

### 2. Очередь задач

- Очередь задач реализована через RabbitMQ
- Каждая задача содержит:
  - `user_id`
  - `link`
  - `type`: group | channel (автоопределяется)
  - `account_id`: null (назначается динамически)
  - `resume_point`: offset\_id или message\_id, если парсинг прерывался
  - `status`: pending | running | paused | completed | failed
- Возможность поставить задачу на паузу / удалить / приостановить из API

### 3. Использование аккаунтов

- Telegram аккаунты подключаются в Integration Service пользователем вручную
- Интеграция с Integration API для получения сессий с полями:
  - `is_banned`, `flood_wait_until`, `is_valid`, `last_used_at`
- Алгоритм распределения:
  - Используются только `valid && !banned && flood_wait_until < now()`
  - Аккаунт с наименьшей нагрузкой (по `last_used_at`)
- Обработка сбоев:
  - Если аккаунт уходит в бан/флуд, задача переключается на другой доступный аккаунт
  - При отсутствии аккаунтов задача уходит в статус `waiting`
  - После появления нового аккаунта или снятия лимитов задача автоматически перезапускается с resume point

### 4. Парсинг

- Используется Telethon с `iter_participants` для групп и `get_messages` для каналов
- Парсится:
  - group: user\_id, username, full name, language\_code, status, join\_date (если возможно)
  - channel: все комментарии (если включены), пользователи-комментаторы, ID, username
  - общая информация: title, username, description, participants\_count
- Обработка ошибок: `FloodWaitError`, `SessionExpiredError`, `AuthKeyError`, `ChannelPrivateError`, `FloodError`, `PhoneMigrateError`
- Лимиты:
  - 200-300 запросов без задержки, далее — адаптивная пауза
  - 100 сообщений/сек безопасно, более — через dynamic backoff
- Парсинг возобновляется при обрыве: offset и позиция сохраняются в Redis

### 5. Интерфейс поиска сообществ по ключевым словам

- Эндпоинт `GET /parser/search?q=футбол&offset=0`
- Поиск по публичным группам и каналам с помощью Telethon/Telegram Bot API (через `search_public_chats` и `GetDialogs`)
- Результаты пагинируются по 100 штук
- Исключаются приватные, пустые, недоступные чаты
- Возможность получить «ещё 100» при скролле или клике пользователя

### 6. Выгрузка результатов

- Эндпоинт `GET /parser/result/{task_id}`
- Поддержка форматов: CSV, JSON, NDJSON
- Данные структурированы: пользователи, чат, дата парсинга, аккаунт, статус задачи
- Пример CSV:

```
user_id,username,full_name,status,join_date,source_link
12345,john_doe,"John Doe",member,2023-01-01,https://t.me/example1
```

### 7. Мониторинг и Webhooks

- Каждая задача логируется: событие, время, аккаунт, ошибка (если есть)
- Статус задачи отслеживается в Redis с TTL
- Возможность push-уведомлений через webhook (в будущем)

### 8. Безопасность

- Все `.session`-файлы запрашиваются только через Vault API
- Используется временный локальный файл, удаляется после завершения работы аккаунта
- Шифрование токенов и внутренних ссылок
- Авторизация по JWT и привязке к user\_id (в API Gateway)

### 9. Масштабирование и многопоточность

- Все задачи асинхронные через Celery
- Парсинг разных чатов — разные задачи
- Аккаунты работают в своих asyncio loop (Telethon не допускает мультипоточности одной сессии)
- Поддержка запуска воркеров на нескольких серверах

### 10. Возможность подключения Proxy-сервиса

- Абстракция proxy-layer
- Возможность задать `proxy_url` на уровне:
  - настройки аккаунта в Integration Service
  - параметра задачи
  - глобального ENV переменного
- Будущая интеграция с `proxy-service` через REST или gRPC

### 11. Ограничения и защита от перегрузок

- Максимальная глубина истории сообщений по умолчанию: 10000 сообщений
- Можно увеличить при наличии достаточного количества аккаунтов
- Ограничение на количество активных задач на одного пользователя (по плану тарифа)
- Ограничения по Telegram лимитам учитываются через динамическую паузу (`FloodWait + random jitter`)
- Все ошибки логируются и метятся как recoverable или fatal

---

## Метрики и мониторинг

- Используется Prometheus + Grafana (или Uptime Kuma)
- Метрики:
  - `parse_tasks_active`
  - `telegram_accounts_available`
  - `telegram_accounts_blocked`
  - `flood_wait_avg`
  - `fail_rate`
  - `resume_count`
- Возможность трассировки задач по `task_id`

---

## Требования к производству

- Тестовая нагрузка: 50 пользователей, 300 аккаунтов, 1000 задач/час
- Продакшен: >1000 пользователей, >10k аккаунтов, до 10k задач/час
- Время отклика API: <500мс при работе очереди
- 99.9% uptime

---

## Технологии и стек

- **Язык**: Python 3.11+
- **Фреймворк API**: FastAPI
- **Очереди**: Celery + RabbitMQ
- **Парсинг**: Telethon (предпочтительно), Pyrogram fallback
- **Хранение**: PostgreSQL, Redis
- **Безопасность**: Vault (session), HTTPS, JWT
- **DevOps**: Docker, docker-compose, Nginx, Prometheus, Grafana

---

## Риски и рекомендации

- Telegram может заблокировать аккаунты при нарушении лимитов — используем FloodWait-aware обёртки, паузы, ротацию аккаунтов
- Если все аккаунты пользователя недоступны — задача уходит в ожидание
- Нет доступа к закрытым чатам без инвайта — эти ошибки считаются `skipped`
- Механизм восстановления задачи по resume\_point обязателен

---

## Этапы реализации (синхронизировано с чек-листом)

1. Подключение сервиса, настройка очередей и БД
2. Реализация очереди и базового API
3. Интеграция с Integration Service для аккаунтов
4. Реализация логики парсинга с учётом лимитов
5. Реализация поиска по ключевым словам
6. Поддержка выгрузки результатов и API-интеграции
7. Поддержка resume, FloodWait и ошибок
8. Поддержка прокси (на уровне интерфейса)
9. Тестирование, нагрузочные прогоны, деплой

---

## Итог

Это ТЗ включает все лучшие практики масштабируемого парсера, встраиваемого в существующую архитектуру проекта, с полной поддержкой многопоточности, безопасности, изоляции по пользователям и возможностью подключения Proxy-сервиса в будущем.

