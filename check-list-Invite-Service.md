# ЧЕК-ЛИСТ РЕАЛИЗАЦИИ INVITE SERVICE

> **Пошаговый план разработки микросервиса Invite Service с детальными задачами и критериями готовности. Каждый пункт должен быть выполнен и протестирован перед переходом к следующему.**

## ФАЗА 1: ИНФРАСТРУКТУРА И БАЗОВАЯ АРХИТЕКТУРА

### ✅ 1.1 Настройка инфраструктуры
- [ ] **Создать структуру проекта** `backend/invite-service/`
  - [ ] Создать папки: `app/`, `migrations/`, `tests/`
  - [ ] Создать подпапки в `app/`: `api/`, `core/`, `models/`, `schemas/`, `services/`, `adapters/`, `workers/`, `utils/`
  - [ ] Создать файлы: `main.py`, `requirements.txt`, `Dockerfile`, `alembic.ini`

- [ ] **Настроить PostgreSQL для Invite Service**
  - [ ] Добавить `invite-postgres` сервис в `docker-compose.yml`
  - [ ] Создать `init.sql` с пользователем `invite_user` и БД `invite_db`
  - [ ] Добавить volume `invite_postgres_data`
  - [ ] Проверить подключение к БД

- [ ] **Добавить Invite Service в docker-compose.yml**
  - [ ] Настроить environment переменные (DATABASE_URL, REDIS_URL, VAULT_*)
  - [ ] Проброс порта `127.0.0.1:8003:8000`
  - [ ] Подключение к сети `backend`
  - [ ] Зависимости от postgres, redis, vault

- [ ] **Настроить базовые зависимости**
  - [ ] FastAPI, SQLAlchemy, asyncpg, alembic
  - [ ] Celery, redis, aiofiles
  - [ ] Telethon для Telegram (начальная интеграция)
  - [ ] hvac для Vault, prometheus-client
  - [ ] pytest, httpx для тестирования

### ✅ 1.2 Базовая конфигурация и модели
- [ ] **Создать core/config.py**
  - [ ] Класс Settings с переменными окружения
  - [ ] Интеграция с Vault (аналогично другим сервисам)
  - [ ] Настройки для разных окружений (dev/prod)
  - [ ] JWT secret получение из Vault

- [ ] **Создать core/vault.py**
  - [ ] VaultClient с AppRole аутентификацией
  - [ ] Методы получения секретов (JWT, Telegram API)
  - [ ] Обработка ошибок подключения
  - [ ] Кэширование токенов

- [ ] **Создать database.py**
  - [ ] Настройка async SQLAlchemy engine
  - [ ] SessionLocal и get_db dependency
  - [ ] База данных подключение и проверка

- [ ] **Создать базовые SQLAlchemy модели**
  - [ ] `models/base.py` - базовые классы
  - [ ] `models/invite_task.py` - главная модель задач
  - [ ] `models/invite_target.py` - целевые пользователи  
  - [ ] `models/invite_task_account.py` - аккаунты в задачах
  - [ ] `models/invite_execution_log.py` - логи выполнения

### ✅ 1.3 Миграции базы данных
- [ ] **Настроить Alembic**
  - [ ] Конфигурация `alembic.ini` и `env.py`
  - [ ] Подключение к async PostgreSQL
  - [ ] Генерация initial migration
  - [ ] Проверка создания всех таблиц и индексов

- [ ] **Создать начальную миграцию**
  - [ ] Все таблицы схемы БД
  - [ ] Индексы для производительности
  - [ ] Constraints и foreign keys
  - [ ] Enum типы для статусов

## ФАЗА 2: ОСНОВНОЕ API И PYDANTIC СХЕМЫ

### ✅ 2.1 Pydantic схемы
- [ ] **Создать schemas/base.py**
  - [ ] Базовые классы для схем
  - [ ] Общие enum'ы (Platform, TaskStatus, Priority)
  - [ ] Утилиты валидации

- [ ] **Создать schemas/invite_task.py**
  - [ ] `InviteTaskCreate` - создание задачи
  - [ ] `InviteTaskUpdate` - обновление задачи
  - [ ] `InviteTaskResponse` - ответ API
  - [ ] `TaskStatusResponse` - статус выполнения

- [ ] **Создать schemas/target.py**
  - [ ] `TargetUserImport` - импорт пользователей
  - [ ] `TargetUserResponse` - информация о пользователе
  - [ ] `FileImportRequest` - загрузка файлов

- [ ] **Создать schemas/statistics.py**
  - [ ] `TaskStatistics` - статистика задачи
  - [ ] `AccountStatus` - статус аккаунта
  - [ ] `ExecutionReport` - финальный отчет

### ✅ 2.2 Базовое FastAPI приложение
- [ ] **Создать main.py**
  - [ ] FastAPI app с базовой конфигурацией
  - [ ] CORS middleware для фронтенда
  - [ ] Exception handlers
  - [ ] Health check endpoint

- [ ] **Создать core/auth.py**
  - [ ] JWT токен валидация
  - [ ] get_current_user dependency
  - [ ] Проверка user_id из токена
  - [ ] Обработка ошибок авторизации

- [ ] **Создать api/v1/endpoints/health.py**
  - [ ] GET `/health` - базовый health check
  - [ ] GET `/health/detailed` - детальная проверка
  - [ ] Проверка БД, Redis, Vault подключений
  - [ ] Prometheus метрики health status

### ✅ 2.3 CRUD сервисы
- [ ] **Создать services/base.py**
  - [ ] Базовый класс CRUDBase
  - [ ] Общие методы create, read, update, delete
  - [ ] Фильтрация по user_id для изоляции

- [ ] **Создать services/invite_task_service.py**
  - [ ] InviteTaskService класс
  - [ ] Методы создания, получения, обновления задач
  - [ ] Фильтрация задач по пользователю
  - [ ] Валидация прав доступа

- [ ] **Создать services/target_service.py**
  - [ ] TargetService для управления целевыми пользователями
  - [ ] Импорт из файлов и parsing-service
  - [ ] Валидация и нормализация данных
  - [ ] Batch операции для производительности

## ФАЗА 3: INTEGRATION SERVICE ИНТЕГРАЦИЯ

### ✅ 3.1 Интеграция с Integration Service
- [ ] **Создать services/integration_client.py**
  - [ ] HTTP клиент для Integration Service API
  - [ ] Методы получения аккаунтов пользователя
  - [ ] Обработка ошибок и ретраи
  - [ ] Кэширование в Redis

- [ ] **Создать services/account_manager.py**
  - [ ] AccountManager класс
  - [ ] Получение активных аккаунтов
  - [ ] Проверка статуса аккаунтов
  - [ ] Управление cooldown'ами

- [ ] **Тестирование интеграции**
  - [ ] Успешное получение аккаунтов
  - [ ] Обработка ошибок недоступности сервиса
  - [ ] Валидация данных аккаунтов
  - [ ] Кэширование работает корректно

### ✅ 3.2 Интеграция с Parsing Service
- [ ] **Создать services/parsing_client.py**
  - [ ] HTTP клиент для Parsing Service API
  - [ ] Получение результатов парсинга
  - [ ] Валидация формата данных
  - [ ] Обработка больших объемов данных

- [ ] **Создать импорт из Parsing Service**
  - [ ] Endpoint для выбора результатов парсинга
  - [ ] Конвертация данных в формат Invite Service
  - [ ] Сохранение связи с исходной задачей парсинга
  - [ ] Обработка ошибок и валидация

## ФАЗА 4: PLATFORM ADAPTERS (TELEGRAM)

### ✅ 4.1 Абстрактный интерфейс Platform Adapter
- [ ] **Создать adapters/base.py**
  - [ ] AbstractInviteStrategy базовый класс
  - [ ] Методы: initialize_client, invite_to_group, send_message
  - [ ] Классы результатов: InviteResult, MessageResult
  - [ ] Rate limiting конфигурация

- [ ] **Создать adapters/factory.py**
  - [ ] PlatformAdapterFactory
  - [ ] Регистрация адаптеров платформ
  - [ ] get_adapter(platform) метод
  - [ ] Валидация поддерживаемых платформ

### ✅ 4.2 Telegram Adapter
- [ ] **Создать adapters/telegram.py**
  - [ ] TelegramInviteStrategy класс
  - [ ] Интеграция с Telethon
  - [ ] Инициализация клиента из session данных
  - [ ] Получение API credentials из Vault

- [ ] **Реализовать основные методы Telegram**
  - [ ] `initialize_client()` - создание TelegramClient
  - [ ] `invite_to_group()` - приглашение в группу/канал
  - [ ] `send_message()` - отправка личного сообщения
  - [ ] `add_to_contacts()` - добавление в контакты

- [ ] **Обработка ошибок Telegram**
  - [ ] FloodWaitError - автоматический cooldown
  - [ ] PrivacyRestrictionError - fallback на сообщения
  - [ ] PeerFloodError - блокировка аккаунта
  - [ ] UserDeactivatedError - недоступный пользователь

- [ ] **Rate limiting для Telegram**
  - [ ] Конфигурация лимитов (40 msg/day, 50 invites/day)
  - [ ] Определение ссылок в сообщениях (лимит 10/day)
  - [ ] Паузы между действиями (10-15 секунд)
  - [ ] Отслеживание использования лимитов

### ✅ 4.3 Проверка прав администратора
- [ ] **Создать utils/telegram_utils.py**
  - [ ] Функция проверки прав админа в группе/канале
  - [ ] Валидация возможности приглашения
  - [ ] Обработка ошибок доступа
  - [ ] Кэширование результатов проверки

## ФАЗА 5: CELERY ВОРКЕРЫ И ВЫПОЛНЕНИЕ ЗАДАЧ

### ✅ 5.1 Настройка Celery
- [ ] **Создать workers/celery_app.py**
  - [ ] Конфигурация Celery app
  - [ ] Подключение к RabbitMQ
  - [ ] Настройка очередей (high, normal, low priority)
  - [ ] Routing правила для задач

- [ ] **Создать workers/config.py**
  - [ ] Celery конфигурация
  - [ ] Настройки воркеров и concurrency
  - [ ] Retry политики
  - [ ] Мониторинг и логирование

### ✅ 5.2 Основные Celery задачи
- [ ] **Создать workers/invite_worker.py**
  - [ ] `execute_invite_task(task_id)` - главная задача
  - [ ] `process_target_batch()` - обработка батча
  - [ ] `reactivate_account()` - возобновление после cooldown
  - [ ] Обработка ошибок и ретраи

- [ ] **Реализовать логику выполнения**
  - [ ] Распределение пользователей по аккаунтам
  - [ ] Параллельное выполнение на разных аккаунтах
  - [ ] Обновление статуса в реальном времени
  - [ ] Логирование всех действий

### ✅ 5.3 Система управления статусами
- [ ] **Создать services/task_execution_service.py**
  - [ ] TaskExecutionService класс
  - [ ] Методы start, pause, resume, cancel
  - [ ] Координация между воркерами
  - [ ] Обновление прогресса в БД

- [ ] **Redis для состояний**
  - [ ] Кэширование статусов задач
  - [ ] Координация между воркерами
  - [ ] Lock'и для предотвращения конфликтов
  - [ ] TTL для автоматической очистки

## ФАЗА 6: API ENDPOINTS

### ✅ 6.1 Управление задачами
- [ ] **Создать api/v1/endpoints/tasks.py**
  - [ ] POST `/tasks` - создание задачи
  - [ ] GET `/tasks` - список задач пользователя
  - [ ] GET `/tasks/{task_id}` - детали задачи
  - [ ] PUT `/tasks/{task_id}` - обновление задачи
  - [ ] DELETE `/tasks/{task_id}` - удаление задачи

- [ ] **Создать api/v1/endpoints/execution.py**
  - [ ] POST `/tasks/{task_id}/start` - запуск
  - [ ] POST `/tasks/{task_id}/pause` - пауза
  - [ ] POST `/tasks/{task_id}/resume` - возобновление
  - [ ] POST `/tasks/{task_id}/cancel` - отмена

### ✅ 6.2 Статистика и отчеты
- [ ] **Создать api/v1/endpoints/statistics.py**
  - [ ] GET `/tasks/{task_id}/status` - текущий статус
  - [ ] GET `/tasks/{task_id}/stats` - детальная статистика
  - [ ] GET `/tasks/{task_id}/report` - финальный отчет
  - [ ] GET `/tasks/{task_id}/logs` - логи выполнения

- [ ] **Реальное время обновления**
  - [ ] Статистика обновляется каждые 10 секунд
  - [ ] Прогресс в процентах
  - [ ] ETA завершения задачи
  - [ ] Статусы всех аккаунтов

### ✅ 6.3 Импорт и валидация данных
- [ ] **Создать api/v1/endpoints/import.py**
  - [ ] POST `/import/file` - загрузка файла (CSV/XLSX/JSON)
  - [ ] POST `/import/parsing` - импорт из parsing-service
  - [ ] GET `/import/validate` - валидация данных
  - [ ] GET `/accounts` - доступные аккаунты

- [ ] **Обработка файлов**
  - [ ] Поддержка CSV, XLSX, JSON форматов
  - [ ] Автоматическое определение столбцов
  - [ ] Валидация форматов username/phone/user_id
  - [ ] Ограничение размера файла (10MB)

## ФАЗА 7: МОНИТОРИНГ И МЕТРИКИ

### ✅ 7.1 Prometheus метрики
- [ ] **Создать utils/metrics.py**
  - [ ] Настройка Prometheus метрик
  - [ ] Counters для задач и результатов
  - [ ] Gauges для активных задач
  - [ ] Histograms для времени выполнения

- [ ] **Интеграция метрик в код**
  - [ ] Метрики в API endpoints
  - [ ] Метрики в Celery задачах
  - [ ] Метрики ошибок и блокировок
  - [ ] Метрики производительности

### ✅ 7.2 Логирование
- [ ] **Настроить структурированное логирование**
  - [ ] JSON формат для ELK интеграции
  - [ ] Логирование действий пользователей
  - [ ] Логирование выполнения задач
  - [ ] Логирование ошибок с context'ом

- [ ] **Создать utils/logging.py**
  - [ ] Кастомные логгеры для разных компонентов
  - [ ] Фильтрация sensitive данных
  - [ ] Ротация логов
  - [ ] Уровни логирования для разных окружений

### ✅ 7.3 Alerting
- [ ] **Настроить правила мониторинга**
  - [ ] High rate блокировок аккаунтов
  - [ ] Длительно висящие задачи
  - [ ] Ошибки интеграции с внешними сервисами
  - [ ] Превышение лимитов Celery очереди

## ФАЗА 8: ТЕСТИРОВАНИЕ

### ✅ 8.1 Unit тесты
- [ ] **Тесты Platform Adapters**
  - [ ] Mock Telegram API ответы
  - [ ] Тестирование rate limiting логики
  - [ ] Обработка различных ошибок
  - [ ] Валидация результатов

- [ ] **Тесты сервисов**
  - [ ] CRUD операции
  - [ ] Бизнес-логика
  - [ ] Валидация данных
  - [ ] Integration Service клиент

### ✅ 8.2 Integration тесты
- [ ] **API endpoints тесты**
  - [ ] Тестирование всех endpoints
  - [ ] JWT авторизация
  - [ ] Валидация запросов/ответов
  - [ ] Обработка ошибок

- [ ] **Database тесты**
  - [ ] Операции с БД
  - [ ] Миграции
  - [ ] Constraints и foreign keys
  - [ ] Производительность запросов

### ✅ 8.3 E2E тесты
- [ ] **Полный workflow тесты**
  - [ ] Создание задачи → выполнение → отчет
  - [ ] Mock интеграции с внешними сервисами
  - [ ] Тестирование pause/resume/cancel
  - [ ] Статистика и логирование

## ФАЗА 9: РАЗВЕРТЫВАНИЕ И PRODUCTION

### ✅ 9.1 Production конфигурация
- [ ] **Vault secrets настройка**
  - [ ] Создание INVITE_SERVICE_ROLE_ID и SECRET_ID
  - [ ] Политики доступа в Vault
  - [ ] JWT secret для сервиса
  - [ ] Telegram API credentials

- [ ] **Docker production build**
  - [ ] Оптимизация Dockerfile
  - [ ] Multi-stage build
  - [ ] Security scanning
  - [ ] Size optimization

### ✅ 9.2 Интеграция в API Gateway
- [ ] **Настроить проксирование**
  - [ ] Добавить routes в API Gateway
  - [ ] `/api/invite/{path}` → invite-service
  - [ ] JWT middleware для авторизации
  - [ ] Rate limiting

- [ ] **Обновить nginx конфигурацию**
  - [ ] Проксирование на invite-service
  - [ ] Load balancing при множественных инстансах
  - [ ] Health checks
  - [ ] Timeouts и retry

### ✅ 9.3 Мониторинг Production
- [ ] **Grafana дашборды**
  - [ ] Метрики производительности
  - [ ] Статусы задач и аккаунтов
  - [ ] Error rates и latency
  - [ ] Celery queue мониторинг

- [ ] **ELK интеграция**
  - [ ] Логи сервиса в Elasticsearch
  - [ ] Kibana дашборды для анализа
  - [ ] Алерты на основе логов
  - [ ] Поиск и фильтрация

## ФАЗА 10: FRONTEND ИНТЕГРАЦИЯ

### ✅ 10.1 Frontend компоненты
- [ ] **Создать страницу Invites**
  - [ ] Список задач пользователя
  - [ ] Создание новой задачи
  - [ ] Управление выполнением
  - [ ] Просмотр статистики

- [ ] **Формы создания задач**
  - [ ] Выбор платформы
  - [ ] Импорт аудитории
  - [ ] Настройка сообщения
  - [ ] Приоритет и расписание

### ✅ 10.2 Real-time обновления
- [ ] **Polling статуса задач**
  - [ ] Автоматическое обновление прогресса
  - [ ] Уведомления о завершении
  - [ ] Ошибки и предупреждения
  - [ ] WebSocket для будущего

---

## КРИТЕРИИ ГОТОВНОСТИ

### ✅ Готовность к тестированию
- [ ] Все базовые endpoints работают
- [ ] Telegram adapter реализован
- [ ] Celery воркеры запускаются
- [ ] БД миграции проходят
- [ ] Health checks отвечают

### ✅ Готовность к production
- [ ] Все тесты проходят (unit + integration)
- [ ] Мониторинг и метрики настроены
- [ ] Vault интеграция работает
- [ ] API Gateway проксирование настроено
- [ ] Frontend базово интегрирован

### ✅ Полная готовность
- [ ] Load тесты пройдены
- [ ] Security audit выполнен
- [ ] Документация API актуальна
- [ ] Runbook для операций готов
- [ ] Backup и recovery процедуры протестированы

---

**При выполнении каждого пункта обязательно проводить тестирование и документировать результаты. Переход к следующей фазе возможен только после полного завершения предыдущей.** 