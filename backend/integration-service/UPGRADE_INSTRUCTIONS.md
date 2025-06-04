# 🔧 Инструкции по обновлению Integration Service

## ⚠️ Критические исправления

Этот апдейт исправляет критические проблемы:
- Vault работает в dev режиме (данные теряются)
- Устаревшие зависимости Telethon
- Проблемы с отправкой кодов Telegram
- Flood ограничения

## 📋 Шаги обновления

### 1. Остановка сервисов
```bash
cd /var/www/html
docker-compose down
```

### 2. Бэкап данных Vault (ВАЖНО!)
```bash
# Если у вас есть важные данные в Vault
docker-compose exec vault vault kv get -format=json kv/integrations/telegram > telegram_backup.json
```

### 3. Пересборка контейнера
```bash
docker-compose build --no-cache integration-service
```

### 4. Запуск с новой конфигурацией
```bash
docker-compose up -d vault
sleep 30  # Ждем инициализации Vault

# Проверяем статус Vault
docker-compose exec vault vault status

# Запускаем остальные сервисы
docker-compose up -d
```

### 5. Инициализация Vault (если нужно)
```bash
# Если Vault не инициализирован
docker-compose exec vault /bin/sh /vault/config/init-vault.sh
```

### 6. Проверка учетных данных
```bash
# Проверяем наличие Telegram credentials
docker-compose exec vault vault kv get kv/integrations/telegram
```

### 7. Если нужно добавить credentials вручную
```bash
docker-compose exec vault vault kv put kv/integrations/telegram \
  api_id="ваш_api_id" \
  api_hash="ваш_api_hash"
```

## 🔍 Проверка работы

### Проверка логов
```bash
docker-compose logs -f integration-service
```

### Проверка Vault
```bash
# Статус
docker-compose exec vault vault status

# Список секретов
docker-compose exec vault vault kv list kv/integrations/
```

### Тестирование API
```bash
curl -X POST http://localhost:8001/v1/telegram/connect \
  -H "Content-Type: application/json" \
  -d '{"phone": "+1234567890"}'
```

## ⚡ Основные изменения

### Vault
- ✅ Production режим вместо dev
- ✅ Персистентное хранение данных
- ✅ Автоматическая инициализация
- ✅ Безопасное хранение ключей

### Telethon
- ✅ Обновлен до версии 1.34.0
- ✅ Убраны deprecated параметры
- ✅ Улучшена обработка flood ошибок
- ✅ Поддержка новых типов кодов

### Обработка ошибок
- ✅ Корректное отображение времени ожидания
- ✅ Обработка заблокированных номеров
- ✅ Улучшенные сообщения об ошибках

## 🚨 Важные заметки

### FLOOD_WAIT ошибки
Если вы получали много ошибок FLOOD_WAIT, нужно подождать 2-4 часа перед следующей попыткой отправки кода.

### Vault ключи
В production среде НЕ сохраняйте ключи Vault в файлах. Используйте внешние системы управления секретами.

### Telegram API
- Коды могут приходить в приложение Telegram вместо SMS
- Это нормальное поведение для новых номеров
- SMS приходят только после нескольких попыток через приложение

## 🔧 Troubleshooting

### Vault не запускается
```bash
# Проверить логи
docker-compose logs vault

# Очистить данные и переинициализировать
docker-compose down -v
docker volume rm vault_data
docker-compose up -d vault
```

### Integration-service не подключается к Vault
```bash
# Проверить сеть
docker-compose exec integration-service ping vault

# Проверить переменные окружения
docker-compose exec integration-service env | grep VAULT
```

### Telegram коды не приходят
1. Проверьте, прошло ли достаточно времени после последней ошибки FLOOD_WAIT
2. Убедитесь, что номер телефона корректный
3. Попробуйте войти через официальное приложение Telegram
4. Проверьте логи на предмет ошибок API

## 📞 Поддержка

Если проблемы сохраняются:
1. Соберите логи: `docker-compose logs > logs.txt`
2. Проверьте статус всех сервисов: `docker-compose ps`
3. Опишите шаги для воспроизведения проблемы 