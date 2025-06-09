# Vault Unsealer Service

Автоматический сервис для unsealing HashiCorp Vault в production среде.

## Особенности

- ✅ **Автоматический unseal** при запуске и перезапуске
- ✅ **Continuous monitoring** - мониторинг статуса Vault 24/7
- ✅ **Production-ready** - retry logic, structured logging, error handling
- ✅ **Security-focused** - minimal permissions, non-root user
- ✅ **Health checks** - интеграция с Docker Compose health checks
- ✅ **Graceful shutdown** - корректная обработка сигналов

## Настройка

### 1. Получение Unseal Keys

При первой инициализации Vault:

```bash
# Инициализация Vault
docker-compose exec vault vault operator init

# Сохраните ВСЕ unseal keys и root token!
# Пример вывода:
# Unseal Key 1: abc123...
# Unseal Key 2: def456...
# Unseal Key 3: ghi789...
# Unseal Key 4: jkl012...
# Unseal Key 5: mno345...
# Initial Root Token: s.xyz789...
```

### 2. Конфигурация Environment Variables

Скопируйте `.env.example` в `.env` и заполните:

```bash
cp .env.example .env
```

Отредактируйте `.env`:

```bash
# Обязательные переменные
VAULT_TOKEN=your-service-token-here
VAULT_UNSEAL_KEY_1=your-first-unseal-key
VAULT_UNSEAL_KEY_2=your-second-unseal-key
VAULT_UNSEAL_KEY_3=your-third-unseal-key
# Опционально для дополнительной безопасности
VAULT_UNSEAL_KEY_4=your-fourth-unseal-key
VAULT_UNSEAL_KEY_5=your-fifth-unseal-key
```

### 3. Запуск

```bash
# Сборка и запуск
docker-compose build vault-unsealer
docker-compose up -d

# Проверка логов
docker-compose logs -f vault-unsealer
```

## Конфигурация

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `VAULT_ADDR` | Адрес Vault сервера | `http://vault:8201` |
| `UNSEALER_MAX_RETRIES` | Максимальное количество попыток подключения | `50` |
| `UNSEALER_RETRY_DELAY` | Задержка между попытками (секунды) | `5` |
| `UNSEALER_MONITOR_INTERVAL` | Интервал мониторинга (секунды) | `30` |
| `UNSEALER_LOG_LEVEL` | Уровень логирования (`DEBUG`, `INFO`, `WARN`, `ERROR`) | `INFO` |

## Логирование

Сервис использует structured logging с временными метками:

```
[2024-01-01T12:00:00.000Z] INFO:  🚀 Vault Unsealer Service starting up
[2024-01-01T12:00:01.000Z] INFO:  Found 5 unseal keys
[2024-01-01T12:00:02.000Z] INFO:  Waiting for Vault to be reachable at http://vault:8201
[2024-01-01T12:00:03.000Z] INFO:  Vault is reachable (attempt 1/50)
[2024-01-01T12:00:04.000Z] INFO:  Starting Vault unseal process
[2024-01-01T12:00:05.000Z] INFO:  Current unseal progress: 0/3
[2024-01-01T12:00:06.000Z] INFO:  Unseal progress: 1/3
[2024-01-01T12:00:07.000Z] INFO:  Unseal progress: 2/3
[2024-01-01T12:00:08.000Z] INFO:  Unseal progress: 3/3
[2024-01-01T12:00:09.000Z] INFO:  ✅ Vault successfully unsealed!
[2024-01-01T12:00:10.000Z] INFO:  ✅ Initial unseal completed successfully
[2024-01-01T12:00:11.000Z] INFO:  Starting continuous Vault monitoring (interval: 30s)
```

## Health Checks

Unsealer service поддерживает Docker health checks:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://vault:8201/v1/sys/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 15s
```

## Troubleshooting

### Проблема: "Insufficient unseal keys"

```bash
# Проверьте, что в .env заданы минимум 3 ключа
grep VAULT_UNSEAL_KEY .env

# Убедитесь, что ключи корректны
docker-compose exec vault vault operator unseal <key>
```

### Проблема: "Vault is not reachable"

```bash
# Проверьте статус Vault
docker-compose logs vault

# Проверьте сеть
docker-compose exec vault-unsealer curl -v http://vault:8201/v1/sys/health
```

### Проблема: "Failed to unseal Vault"

```bash
# Проверьте логи детально
docker-compose logs vault-unsealer

# Ручная проверка ключей
docker-compose exec vault vault status
```

## Security

- 🔐 **Non-root user**: Сервис работает от непривилегированного пользователя
- 🔐 **Minimal network access**: Доступ только к Vault API
- 🔐 **Environment isolation**: Unseal keys только в переменных окружения
- 🔐 **No key logging**: Ключи никогда не попадают в логи
- 🔐 **Graceful shutdown**: Корректная обработка сигналов остановки

## Production Considerations

1. **Backup unseal keys** в нескольких безопасных местах
2. **Monitor unsealer logs** через систему мониторинга
3. **Set up alerts** на failed unseal operations
4. **Regular testing** процедуры восстановления
5. **Key rotation** план для периодической смены ключей

## Интеграция с Docker Compose

Unsealer автоматически интегрируется с зависимостями:

```yaml
depends_on:
  vault:
    condition: service_healthy  # Ждёт unsealed Vault
  vault-unsealer:
    condition: service_started  # Ждёт готовности unsealer
```

Это гарантирует, что все сервисы запустятся только после полного unsealing Vault. 