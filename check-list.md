# CHECK LIST: Подготовка инфраструктуры до и после проектирования микросервисов

---

## 1. Что нужно сделать сейчас (до появления архитектуры микросервисов)

### 1.1. Базовая инфраструктура
- [x] Настроить и протестировать Docker Compose, сети, volume, базовые сервисы (MySQL, Redis, RabbitMQ, Vault, Prometheus, Grafana, ELK)
  - [x] Все сервисы стартуют и доступны по нужным адресам
  - [x] Все volumes и сети корректно проброшены
  - [x] Нет лишних открытых портов наружу
- [x] Централизованное логирование (Logstash → Elasticsearch → Kibana)
  - [x] Logstash видит и обрабатывает тестовые логи
  - [x] В Elasticsearch появляются индексы logs-*
  - [x] Kibana подключена к Elasticsearch
  - [ ] Kibana не может создать служебный индекс .kibana_7.17.0 (ошибка index_not_found_exception). Требуется убедиться, что Elasticsearch полностью готов до старта Kibana, и проверить права на создание индексов. Проблема не блокирует работу ELK, но мешает пользоваться интерфейсом Kibana.
- [x] Мониторинг инфраструктуры (Prometheus, Grafana)
  - [x] Проверить, что метрики собираются и отображаются в Grafana
- [x] Vault (секреты и управление доступом)
  - [x] Vault стартует в dev-режиме, успешно инициализируется и unseal
  - [x] Переведен в production-режим с файловым хранением и персистентными данными
- [x] Админ-панели доступны только из доверенных сетей (через внутреннюю docker-сеть или SSH-туннель)
- [ ] Настроить домен и DNS-записи (добавить A-запись на сервер, проверить доступность)
  - [ ] Домен настроен, указывает на сервер
  - [ ] DNS-записи корректны
  - [ ] Проверена доступность домена снаружи
- [x] Настроить HTTPS для публичных сервисов (API Gateway и фронт)
  - [x] Сертификаты установлены (Let's Encrypt)
  - [x] Работает автоматическое обновление сертификатов (через certbot renew и cron)
  - [x] nginx обслуживает и http, и https, реализован редирект на https
- [ ] Настроить хранение секретов (Vault)
  - [ ] Vault доступен только из backend-сети
  - [ ] Секреты можно безопасно получать из Vault
- [ ] Проверить автоматический деплой (CI/CD)
  - [ ] Изменения из репозитория попадают на сервер
  - [ ] Деплой не требует ручных действий
- [ ] Документировать инфраструктуру
  - [ ] Описаны все доступы, пароли, токены, адреса сервисов (в защищённом месте)
  - [ ] Описана структура docker-compose, связи между сервисами, порты, volume
  - [ ] Описан процесс деплоя, обновления, восстановления
  - [ ] Описан процесс добавления нового сервиса
- [ ] Smoke-тесты инфраструктуры
  - [ ] Проверить, что все сервисы стартуют с нуля (docker-compose up)
  - [ ] Проверить, что все сервисы корректно завершают работу (docker-compose down)
  - [ ] Проверить, что все переменные окружения заданы и не содержат секретов в открытом виде
  - [ ] Проверить, что все контейнеры используют только необходимые volume и сети
- [x] Vault запущен в production-режиме с файловым хранением, unseal keys настроены
- [x] Проверена доступность Vault через curl
- [x] Все сервисы могут обращаться к Vault по адресу http://vault:8201 
- [x] ✅ Vault готов к продакшену: production-режим, персистентное хранение, безопасность
- [x] Настроить алерты в Alertmanager
- [ ] Создать пользовательские дашборды в Grafana
- [x] Пробросить порты админских сервисов только на 127.0.0.1
- [x] Проверить доступ к админским сервисам только через SSH-туннель
- [x] Убедиться, что наружу открыты только 80 и 443
- [x] Вынести все секреты (пароли, токены, ключи) в Vault (частично: CSRF/JWT для API Gateway)
- [x] Реализовать получение секретов из Vault хотя бы в одном сервисе (API Gateway)
- [ ] Убрать секреты из .env и docker-compose, оставить только VAULT_ADDR и VAULT_TOKEN
- [ ] Реализовать админку (мониторинг пользователей, расходы, оплаты, дашборды, логи)
- [ ] Реализовать пользовательский аккаунт (регистрация, личный кабинет, история оплат, интеграции)
- [ ] Обеспечить безопасность фронта (HTTPS, JWT, секреты только через Vault, audit trail)
- [x] Swagger UI и ReDoc отключены во внешней среде, доступны только при DEBUG=true
- [x] OpenAPI JSON остаётся доступен для интеграций
- [x] Логирование (audit trail) теперь реализовано для login, logout, register, ошибок аутентификации. Все логи в формате JSON для Logstash/ELK
- [x] Security схемы (JWT, CSRF) описаны в OpenAPI/Swagger
- [x] Интеграция auth (регистрация и логин) через API Gateway завершена, фронт после регистрации делает автоматический логин
- [x] После регистрации автоматически выполнять логин и сохранять токены
- [ ] Добавить капчу на регистрацию
- [ ] Добавить email-валидацию при регистрации

---

## 2. Что делать после появления архитектуры микросервисов

- Создать отдельные базы данных для каждого микросервиса
- Настроить пользователей и права доступа для каждого сервиса
- Реализовать и протестировать миграции схем
- Настроить очереди в RabbitMQ для всех сервисов, которые будут использовать асинхронные задачи
- Настроить кэширование в Redis (разделить пространства ключей для разных сервисов)
- Протестировать работу очередей и кэша
- Стандартизировать формат логов, трассировку, интеграцию с Logstash
- Настроить дашборды и алерты для бизнес-метрик микросервисов
- Реализовать smoke-тесты, интеграционные тесты, тестовые данные для сервисов
- Настроить CI/CD для микросервисов
- Описать процесс деплоя, обновления, восстановления для каждого сервиса

---

> **Этот файл — рабочий чек-лист подготовки инфраструктуры. Отмечайте выполненные пункты и дополняйте по мере развития проекта.**

> Базовая инфраструктура функционирует, мониторинг работает. Следующий шаг — настройка алертов и дашбордов. 

> Алерты успешно отображаются в веб-интерфейсе Alertmanager, интеграция с Prometheus работает. Следующий шаг — создание пользовательских дашбордов в Grafana. 

> **2025-06-04:** Integration Service полностью готов к production - Vault в production режиме, Telegram интеграция работает, SMS коды доставляются, аккаунты подключаются успешно. Все критические проблемы решены. 