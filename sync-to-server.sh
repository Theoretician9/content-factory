#!/bin/bash

# Пути
LOCAL_PATH="/c/Users/nikit/cod/content-factory"
REMOTE_PATH="/var/www/html"
SERVER="92.113.146.148"

# Проверяем наличие rsync
if ! command -v rsync &> /dev/null; then
    echo "rsync не установлен. Устанавливаем..."
    pacman -S rsync --noconfirm
fi

# Синхронизация
echo "Начинаем синхронизацию..."
rsync -avz --delete "$LOCAL_PATH/" "root@$SERVER:$REMOTE_PATH/"

# Проверяем результат
if [ $? -eq 0 ]; then
    echo "Синхронизация успешно завершена"
else
    echo "Ошибка при синхронизации"
    exit 1
fi 