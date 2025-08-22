# Команды для исправления проблемы с enum taskstatus

## 1. Подключение к серверу
```bash
ssh -i C:\Users\nikit\.ssh\server_key admin@telegraminvi.vps.webdock.cloud
```

## 2. Переход в рабочую директорию
```bash
cd /var/www/html
```

## 3. Создание enum типов в PostgreSQL (если нужно вручную)
```bash
# Подключение к PostgreSQL контейнеру
docker-compose exec postgres-invite psql -U invite_user -d invite_db

# Выполнение SQL команд для создания enum типов
\i /docker-entrypoint-initdb.d/create_enums.sql

# Проверка созданных типов
SELECT typname FROM pg_type WHERE typname IN ('taskstatus', 'taskpriority', 'targetstatus', 'targetsource', 'inviteresultstatus');

# Выход из PostgreSQL
\q
```

## 4. Перезапуск сервисов
```bash
# Остановка сервисов
docker-compose stop invite-service invite-worker

# Перезапуск с пересборкой
docker-compose up -d --build invite-service invite-worker

# Проверка логов
docker-compose logs -f invite-service --tail 50
docker-compose logs -f invite-worker --tail 50
```

## 5. Проверка работы
```bash
# Проверка health check
curl -X GET "http://localhost:8002/api/v1/health/"

# Проверка создания задач
curl -X GET "http://localhost:8002/api/v1/tasks/"
```

## 6. Если проблемы с enum типами остаются
```bash
# Удаление старых таблиц (ОСТОРОЖНО!)
docker-compose exec postgres-invite psql -U invite_user -d invite_db -c "DROP TABLE IF EXISTS invite_execution_logs CASCADE;"
docker-compose exec postgres-invite psql -U invite_user -d invite_db -c "DROP TABLE IF EXISTS invite_targets CASCADE;"
docker-compose exec postgres-invite psql -U invite_user -d invite_db -c "DROP TABLE IF EXISTS invite_tasks CASCADE;"

# Удаление старых enum типов
docker-compose exec postgres-invite psql -U invite_user -d invite_db -c "DROP TYPE IF EXISTS taskstatus CASCADE;"
docker-compose exec postgres-invite psql -U invite_user -d invite_db -c "DROP TYPE IF EXISTS taskpriority CASCADE;"

# Перезапуск invite-service для пересоздания таблиц
docker-compose restart invite-service
```
