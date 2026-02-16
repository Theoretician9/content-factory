# Evolution Agent — сборка, деплой и тесты

Документ составлен по данным из **PROJECT**, **PROJECT-STATUS.md** и **Rules.md**. Код выполняется на сервере, не на localhost.

---

## 1. Окружение

| Параметр | Значение |
|----------|----------|
| Сервер | 92.113.146.148 |
| Домен | https://content-factory.xyz/ |
| Корневой каталог на сервере | `/var/www/html` |
| API (внешний) | https://content-factory.xyz/api/agents/… (прокси через nginx → api-gateway → evolution-agent) |
| SSH | `ssh -i C:\Users\nikit\.ssh\server_key admin@telegraminvi.vps.webdock.cloud` |
| SSH с туннелем (Vault, Grafana, Kibana и т.д.) | `ssh -i C:\Users\nikit\.ssh\server_key -L 3000:localhost:3000 -L 9090:localhost:9090 -L 5601:localhost:5601 -L 9093:localhost:9093 -L 8201:localhost:8201 -L 15672:localhost:15672 -L 9600:localhost:9600 -L 9200:localhost:9200 admin@telegraminvi.vps.webdock.cloud` |

После пуша в GitHub код деплоится на сервер; команды ниже выполняются **на сервере** (или через SSH), если не указано иное.

---

## 2. Подготовка Vault (на сервере)

Evolution-agent читает секреты из Vault KV v2. Логические пути в коде: `jwt`, `openai`, `evolution-agent/gemini`, `evolution-agent/groq`, `evolution-agent/db` — соответствуют путям в mount `kv`.

Выполнять **внутри контейнера Vault** или с хоста, где настроен `vault` CLI и доступ к Vault (например, через туннель `localhost:8201`):

```bash
# 1. JWT (если ещё не создан — используется и другими сервисами)
vault kv put kv/jwt secret_key="<твой-секрет-для-подписи-JWT>"

# 2. OpenAI (Content Agent — GPT-4o-mini)
vault kv put kv/openai api_key="sk-..."

# 3. Gemini (Research Agent — Gemini 1.5 Flash)
vault kv put kv/evolution-agent/gemini api_key="<GEMINI_API_KEY>"

# 4. Groq (Persona/Strategy — Llama 3.1 8B)
vault kv put kv/evolution-agent/groq api_key="gsk_..."

# 5. Строка подключения к БД evolution_db (если не задаётся через .env)
vault kv put kv/evolution-agent/db database_url="postgresql+asyncpg://evolution_user:evolution_password@evolution-postgres:5432/evolution_db"
```

Если используешь политики по путям (как в PROJECT): для evolution-agent нужен доступ к `kv/data/jwt`, `kv/data/openai`, `kv/data/evolution-agent/*`. Роль для сервиса и политику создаёшь по шагам из PROJECT (AppRole + policy для `kv/data/...`).

---

## 2a. Откуда взять EVOLUTION_VAULT_ROLE_ID и EVOLUTION_VAULT_SECRET_ID

Эти значения **не придумываются** — их выдаёт Vault после создания роли AppRole для evolution-agent. Делается один раз на сервере (или с машины с доступом к Vault).

### Шаг 1: Подключиться к Vault

На сервере, из каталога проекта:

```bash
cd /var/www/html
docker compose exec vault sh
```

Внутри контейнера доступна команда `vault`. Либо, если `vault` CLI установлен на хосте и поднят туннель на 8201:

```bash
export VAULT_ADDR=http://127.0.0.1:8201
export VAULT_TOKEN=<твой_root_токен_vault>
```

### Шаг 2: Создать политику для evolution-agent

В контейнере Vault (или с хоста с настроенным `VAULT_ADDR` и `VAULT_TOKEN`):

```bash
vault policy write evolution-agent-policy - <<EOF
# Evolution Agent: JWT, OpenAI, Gemini, Groq, DB
path "kv/data/jwt" {
  capabilities = ["read"]
}
path "kv/data/openai" {
  capabilities = ["read"]
}
path "kv/data/evolution-agent/*" {
  capabilities = ["read"]
}
EOF
```

### Шаг 3: Создать AppRole-роль

```bash
vault write auth/approle/role/evolution-agent \
  token_policies=evolution-agent-policy \
  token_ttl=24h \
  token_max_ttl=24h \
  secret_id_num_uses=0 \
  token_num_uses=0 \
  bind_secret_id=true
```

Если Vault в контейнере и команда выше выполняется с хоста (не из `docker compose exec vault sh`), то сначала задай переменные:

```bash
export VAULT_ADDR=http://vault:8201
```

изнутри другого контейнера в той же сети не получится — тогда все команды выполняй **внутри контейнера vault** (`docker compose exec vault sh`), а там по умолчанию `VAULT_ADDR` уже может указывать на localhost; если Vault слушает на 0.0.0.0, оставь `VAULT_ADDR=http://127.0.0.1:8200` или как у тебя настроено. Либо выполни шаги 2–5 одной оболочкой внутри контейнера:

```bash
docker compose exec vault sh
# внутри:
export VAULT_TOKEN=<root_token>
vault policy write evolution-agent-policy - <<'EOF'
path "kv/data/jwt" { capabilities = ["read"] }
path "kv/data/openai" { capabilities = ["read"] }
path "kv/data/evolution-agent/*" { capabilities = ["read"] }
EOF
vault write auth/approle/role/evolution-agent token_policies=evolution-agent-policy token_ttl=24h token_max_ttl=24h secret_id_num_uses=0 token_num_uses=0 bind_secret_id=true
vault read auth/approle/role/evolution-agent/role-id
vault write -f auth/approle/role/evolution-agent/secret-id
exit
```

### Шаг 4: Получить role_id

```bash
vault read auth/approle/role/evolution-agent/role-id
```

В выводе будет строка **`role_id`** (UUID). Это значение вписываешь в `.env` как **`EVOLUTION_VAULT_ROLE_ID`**.

### Шаг 5: Сгенерировать secret_id

```bash
vault write -f auth/approle/role/evolution-agent/secret-id
```

В выводе будет **`secret_id`** (UUID). Это значение вписываешь в `.env` как **`EVOLUTION_VAULT_SECRET_ID`**.

### Шаг 6: Вписать в .env на сервере

На сервере открой `.env` в корне проекта (`/var/www/html/.env`) и добавь (или замени) строки, подставив реальные значения из шагов 4 и 5:

```bash
EVOLUTION_VAULT_ROLE_ID=<значение role_id из шага 4>
EVOLUTION_VAULT_SECRET_ID=<значение secret_id из шага 5>
```

Сохрани файл. Перезапусти evolution-agent:

```bash
docker compose restart evolution-agent
```

**Итог:** `EVOLUTION_VAULT_ROLE_ID` и `EVOLUTION_VAULT_SECRET_ID` ты берёшь из Vault командами `vault read .../role-id` и `vault write -f .../secret-id` после создания роли `evolution-agent` и политики `evolution-agent-policy`.

---

## 3. Переменные окружения на сервере

В каталоге проекта на сервере (`/var/www/html`) в файле **`.env`** должны быть заданы (в дополнение к уже существующим):

```bash
# Evolution Agent — AppRole для Vault (значения из раздела 2a выше)
EVOLUTION_VAULT_ROLE_ID=<role_id_из_vault>
EVOLUTION_VAULT_SECRET_ID=<secret_id_из_vault>

# Общие для Vault (если ещё не заданы)
VAULT_ADDR=http://vault:8201
# VAULT_TOKEN=...  # опционально, fallback
```

Файл `.env` не коммитить в репозиторий. При необходимости прав на сервере — редактировать вручную (например, `nano .env` после `cd /var/www/html`).

---

## 4. Сборка и запуск контейнеров (на сервере)

Все команды — из **корневого каталога проекта на сервере** (`/var/www/html`):

```bash
cd /var/www/html

# Сборка только evolution-agent (и при необходимости зависимостей)
docker compose build evolution-agent

# Запуск PostgreSQL для evolution-agent и самого сервиса
docker compose up -d evolution-postgres evolution-agent

# Проверка логов
docker compose logs -f evolution-agent
```

Проверка здоровья через API Gateway (снаружи):

```bash
curl -s https://content-factory.xyz/health
```

Либо изнутри сети Docker (с сервера):

```bash
docker compose exec evolution-agent curl -s http://localhost:8000/health
```

Ожидаемый ответ от evolution-agent: `{"status":"healthy","service":"Evolution Agent Service","version":"0.1.0"}`.

---

## 5. Миграции БД (evolution_db)

В образе evolution-agent рабочая директория `/app`, там же лежит `alembic.ini`. При первом запуске или после изменений схемы:

```bash
cd /var/www/html
docker compose exec evolution-agent sh -c "cd /app && alembic upgrade head"
```

---

## 6. Ручной e2e-сценарий (без Celery)

Используется **внешний URL** https://content-factory.xyz и **JWT пользователя** (получить через логин на фронте или через API Gateway `/api/auth/login`).

**6.1. Онбординг агента**

```bash
curl -X POST "https://content-factory.xyz/api/agents/onboard" \
  -H "Authorization: Bearer <USER_JWT>" \
  -H "Content-Type: application/json" \
  -d "{\"channel_id\": \"<telegram_channel_id_или_username>\", \"description\": \"Веди канал про X в стиле Y\", \"tone\": \"дружелюбный эксперт\", \"language\": \"ru\"}"
```

В ответе ожидаются `strategy_id` и массив из 7 слотов.

**6.2. Календарь**

```bash
curl -s "https://content-factory.xyz/api/agents/calendar?channel_id=<telegram_channel_id_или_username>" \
  -H "Authorization: Bearer <USER_JWT>"
```

**6.3. Принудительный запуск генерации (force-run)**

Подставь реальные `channel_id` и диапазон дат по своим слотам:

```bash
curl -X POST "https://content-factory.xyz/api/agents/force-run" \
  -H "Authorization: Bearer <USER_JWT>" \
  -H "Content-Type: application/json" \
  -d "{\"channel_id\": \"<telegram_channel_id_или_username>\", \"from_dt\": \"2025-01-01T00:00:00Z\", \"to_dt\": \"2025-12-31T23:59:59Z\"}"
```

Проверь в ответе статусы слотов и появление поста в Telegram-канале.

**6.4. Регенерация слота с фидбеком**

`<slot_id>` — UUID слота из календаря:

```bash
curl -X POST "https://content-factory.xyz/api/agents/slots/<slot_id>/regenerate" \
  -H "Authorization: Bearer <USER_JWT>" \
  -H "Content-Type: application/json" \
  -d "{\"feedback\": \"Сделать короче и менее формально\"}"
```

---

## 7. Celery worker и beat (по желанию)

Для автоматического ежедневного цикла без ручного `force-run` на сервере поднимают воркер и beat.

**7.1. Воркер (в отдельном терминале или через отдельный контейнер)**

```bash
cd /var/www/html
docker compose exec -it evolution-agent bash
# внутри контейнера:
celery -A app.workers.celery_app.celery_app worker --loglevel=info
```

**7.2. Beat (второй терминал или отдельный контейнер)**

```bash
cd /var/www/html
docker compose exec -it evolution-agent bash
# внутри контейнера:
celery -A app.workers.celery_app.celery_app beat --loglevel=info
```

Redis для Celery в docker-compose уже используется как `redis:6379` (внутренний адрес); брокер и backend заданы в `app.workers.celery_app` как `redis://redis:6379/0`.

---

## 8. Полезные команды на сервере

```bash
cd /var/www/html

# Логи evolution-agent
docker compose logs evolution-agent --tail 100

# Логи api-gateway (прокси к evolution-agent)
docker compose logs api-gateway --tail 50

# Перезапуск evolution-agent
docker compose restart evolution-agent

# Подключение к контейнеру
docker compose exec evolution-agent bash
```

---

## 9. Краткие рекомендации

- **Секреты**: только в Vault; в `.env` на сервере — только `VAULT_ADDR`, при необходимости `EVOLUTION_VAULT_ROLE_ID` и `EVOLUTION_VAULT_SECRET_ID` (и общий `VAULT_TOKEN` только как fallback).
- **Правки .env**: делать на сервере вручную (например, `nano .env`); не коммитить секреты в репозиторий.
- **Публичный доступ к API**: только через https://content-factory.xyz (nginx → api-gateway → evolution-agent). Прямой доступ к evolution-agent только из backend-сети Docker.
- **Проверка после деплоя**: health, затем onboard → calendar → force-run → проверка поста в Telegram и при необходимости regenerate.

Все команды рассчитаны на выполнение тобой; автоматически они не выполняются.
