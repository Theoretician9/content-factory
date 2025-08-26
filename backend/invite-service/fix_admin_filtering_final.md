# Исправление проблем с админской фильтрацией

## Выявленные проблемы

По логам обнаружены 2 критические проблемы:

1. **❌ group_id отсутствует в настройках задачи**
   ```
   WARNING: Задача 54 не содержит group_id в настройках, используем базовую фильтрацию
   ```

2. **❌ 404 ошибка при отправке приглашений**
   ```
   ERROR: Client error '404 Not Found' for url 'http://integration-service:8000/api/v1/telegram/invites/accounts/7d46a75a-29f3-4b49-b29b-e11799136012/invite'
   ```

## Исправления

### 1. Исправлены неправильные URL в integration_client.py
- **Старый URL**: `/api/v1/telegram/invites/accounts/{account_id}/invite` ❌
- **Новый URL**: `/api/v1/telegram/accounts/{account_id}/invite` ✅

**Файлы изменены**:
- `app/services/integration_client.py` - исправлены пути для invite, message, limits

### 2. Добавлены поля в схему настроек задачи
Добавлены новые поля в `TaskSettingsSchema`:
- `group_id: Optional[str]` - ID группы/канала для проверки админских прав  
- `invite_type: Optional[str]` - тип приглашения (по умолчанию "group_invite")

**Файлы изменены**:
- `app/schemas/invite_task.py` - добавлены поля group_id и invite_type

### 3. Создан эндпоинт проверки админских прав
Добавлен новый эндпоинт в integration-service:
- `/api/v1/telegram/accounts/{account_id}/check-admin`
- Проверяет реальные админские права через Telegram API
- Возвращает is_admin, permissions, has_required_permissions

**Файлы изменены**:
- `../integration-service/app/api/v1/endpoints/telegram_invites.py` - добавлен эндпоинт check-admin

## Ожидаемый результат

После применения исправлений:

**Новые логи вместо старых**:
```
# Старые логи (проблемные):
WARNING: Задача 54 не содержит group_id в настройках, используем базовую фильтрацию
ERROR: Client error '404 Not Found' for url '...'

# Новые логи (исправленные):
INFO: Проверяем админские права для группы foothub123 для 3 аккаунтов
✅ Аккаунт XXX является администратором группы foothub123 с правами приглашать
❌ Аккаунт YYY НЕ является администратором группы foothub123 или не имеет прав приглашать  
❌ Аккаунт ZZZ НЕ является администратором группы foothub123 или не имеет прав приглашать
INFO: Фильтрация аккаунтов: из 3 доступно 1 админских аккаунтов
```

## Команды для перезапуска

```bash
# Перезапуск сервисов для применения изменений
docker-compose restart invite-service invite-worker integration-service

# Проверка логов
docker-compose logs invite-worker --tail 50
docker-compose logs integration-service --tail 50
```

## Что нужно настроить на фронтенде

Для полной работы админской фильтрации фронтенд должен передавать `group_id` в настройках задачи:

```json
{
  "name": "Приглашения в группу",
  "platform": "telegram", 
  "settings": {
    "group_id": "@foothub123",  // ← ОБЯЗАТЕЛЬНО для админской фильтрации
    "invite_type": "group_invite"
  }
}
```

**Важно**: Без `group_id` в настройках воркер будет использовать базовую фильтрацию (только активность + лимиты) вместо проверки реальных админских прав.