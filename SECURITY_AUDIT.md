# Security Audit и план улучшений

## Текущий статус безопасности

### Реализовано
1. Базовая защита API Gateway
   - Rate limiting на основные эндпоинты
   - CORS настройки
   - Базовая JWT аутентификация

2. Мониторинг и логирование
   - Prometheus + Grafana для метрик
   - Elasticsearch + Kibana для логов
   - Alertmanager для алертов

3. Базовая изоляция сервисов
   - Docker networks
   - Health checks
   - Базовые security headers

4. Начальная настройка Vault
   - Добавлен сервис Vault в docker-compose
   - Создан базовый конфиг
   - Реализован Python-клиент
   - Подготовлен скрипт инициализации
   - Интегрирован с Integration Service

### Требует внимания
1. Управление секретами
   - [x] Базовая настройка Vault
   - [x] Интеграция с Integration Service
   - [ ] Миграция секретов из .env
   - [ ] Настройка RBAC в Vault
   - [ ] Интеграция с остальными микросервисами

2. Защита API Gateway
   - Отсутствует WAF
   - Не настроен HTTPS
   - Базовый rate limiting

3. Аудит и мониторинг
   - Неполное логирование
   - Отсутствие audit trail
   - Недостаточные алерты

## План улучшений

### 1. Централизованное управление секретами (Vault)
- [x] Внедрение HashiCorp Vault
  - [x] Настройка Vault в dev режиме
  - [x] Создание базовых секретов
  - [x] Интеграция с Integration Service
  - [ ] Интеграция с остальными микросервисами
  - [ ] Миграция секретов из .env
  - [ ] Настройка RBAC в Vault

### 2. Усиление безопасности API Gateway
- [ ] Настройка HTTPS (Let's Encrypt)
- [ ] Внедрение WAF
- [ ] Улучшение rate limiting
- [ ] Усиление JWT авторизации
- [ ] Настройка CORS whitelist

### 3. Аудит и мониторинг безопасности
- [ ] Централизованное логирование
- [ ] Внедрение audit trail
- [ ] Настройка security алертов
- [ ] Мониторинг подозрительной активности

### 4. Усиление защиты микросервисов
- [ ] Изоляция в Docker overlay network
- [ ] Настройка health checks
- [ ] Внедрение circuit breakers
- [ ] Настройка TLS между сервисами

### 5. Безопасность данных
- [ ] Шифрование данных в rest
- [ ] Шифрование данных в transit
- [ ] Настройка backup процедур
- [ ] Внедрение data retention policies

### 6. Автоматизация безопасности
- [ ] Сканирование на уязвимости (CVE)
- [ ] Security checks в CI/CD
- [ ] Автообновление зависимостей
- [ ] Security тесты

### 7. Документация по безопасности
- [ ] Security guidelines
- [ ] Процедуры безопасности
- [ ] Runbooks для инцидентов
- [ ] Security best practices в README

## Приоритеты
1. Vault (управление секретами)
2. API Gateway (rate limiting, WAF)
3. Аудит и мониторинг
4. Остальные улучшения

## Текущий фокус
Внедрение HashiCorp Vault для централизованного управления секретами.

### Следующие шаги по Vault:
1. [x] Добавление Vault в docker-compose.yml
2. [x] Настройка базовой конфигурации
3. [x] Создание первых секретов
4. [x] Интеграция с Integration Service
5. [ ] Миграция остальных секретов

### Следующий шаг:
Интеграция Vault с остальными микросервисами (User Service, Billing Service и т.д.).

## 2024-05-27
- Все админские сервисы (Grafana, Prometheus, Alertmanager, Kibana, Vault, RabbitMQ Management, Logstash Monitoring, Elasticsearch) проброшены только на 127.0.0.1 сервера.
- Доступ к ним возможен только через SSH-туннель.
- Наружу порты не проброшены, безопасность усилена.

## 2024-05-28
- Начат переход на централизованное хранение секретов в HashiCorp Vault.
- Определена структура хранения: secret/<service>/<ключ> (например, secret/mysql/root_password, secret/user-service/secret_key).
- Пример записи секрета: vault kv put secret/mysql root_password=... user=... user_password=...
- Пример получения секрета в Python через hvac или vault_client.
- Постепенно все сервисы будут получать секреты из Vault, а не из .env/docker-compose.
- В docker-compose и .env останутся только VAULT_ADDR и VAULT_TOKEN.
- Для домена content-factory.xyz настроен HTTPS (Let's Encrypt), сертификаты выпускаются и продлеваются через certbot.
- nginx обслуживает и http, и https, реализован автоматический редирект на https.
- Для автоматического продления сертификата используется команда: docker-compose run --rm certbot renew && docker-compose restart nginx (рекомендуется добавить в cron).
- Безопасность внешнего трафика усилена.
- CSRF_SECRET_KEY и JWT_SECRET_KEY для API Gateway вынесены в Vault, .env не содержит этих секретов в открытом виде.
- Интеграция с Vault реализована для API Gateway, продолжается для остальных сервисов.
- Swagger UI и ReDoc отключены во внешней среде, доступны только при DEBUG=true.
- OpenAPI JSON остаётся доступен для интеграций.
- Логирование (audit trail) теперь реализовано для login, logout, register, ошибок аутентификации. Все логи в формате JSON для Logstash/ELK.
- Security схемы (JWT, CSRF) описаны в OpenAPI/Swagger. 