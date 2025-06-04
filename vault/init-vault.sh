#!/bin/bash

# Скрипт для инициализации Vault в production режиме
# Запускается после первого старта Vault

export VAULT_ADDR="http://vault:8201"

echo "Ожидание запуска Vault..."
sleep 10

# Проверяем статус Vault
vault_status=$(vault status -format=json 2>/dev/null | jq -r '.initialized // false')

if [ "$vault_status" = "false" ]; then
    echo "Инициализируем Vault..."
    
    # Инициализируем с 1 ключом (для простоты)
    init_output=$(vault operator init -key-shares=1 -key-threshold=1 -format=json)
    
    # Извлекаем ключи
    unseal_key=$(echo $init_output | jq -r '.unseal_keys_b64[0]')
    root_token=$(echo $init_output | jq -r '.root_token')
    
    echo "Vault инициализирован!"
    echo "Root token: $root_token"
    echo "Unseal key: $unseal_key"
    
    # Сохраняем ключи (В PRODUCTION НЕ ДЕЛАТЬ ТАК!)
    echo "$root_token" > /vault/data/root_token
    echo "$unseal_key" > /vault/data/unseal_key
    
    # Разблокируем Vault
    vault operator unseal $unseal_key
    
    # Авторизуемся
    vault auth $root_token
    
    # Включаем KV v2 движок
    vault secrets enable -version=2 kv
    
    # Добавляем начальные секреты Telegram
    if [ ! -z "$TELEGRAM_API_ID" ] && [ ! -z "$TELEGRAM_API_HASH" ]; then
        vault kv put kv/integrations/telegram \
            api_id="$TELEGRAM_API_ID" \
            api_hash="$TELEGRAM_API_HASH" \
            webhook_url="" \
            proxy=""
        echo "Добавлены учетные данные Telegram"
    fi
    
    echo "Vault успешно настроен!"
else
    echo "Vault уже инициализирован"
    
    # Проверяем заблокирован ли Vault
    sealed_status=$(vault status -format=json 2>/dev/null | jq -r '.sealed // true')
    
    if [ "$sealed_status" = "true" ]; then
        echo "Vault заблокирован, пытаемся разблокировать..."
        
        if [ -f "/vault/data/unseal_key" ]; then
            unseal_key=$(cat /vault/data/unseal_key)
            vault operator unseal $unseal_key
            echo "Vault разблокирован"
        else
            echo "Ключ разблокировки не найден! Vault останется заблокированным."
        fi
    fi
fi 