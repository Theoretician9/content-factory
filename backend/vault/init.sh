#!/bin/bash

# Ждем пока Vault будет готов
until curl -s http://vault:8200/v1/sys/health | grep -q "initialized"; do
  echo "Waiting for Vault to be ready..."
  sleep 2
done

# Проверяем, инициализирован ли Vault
INITIALIZED=$(curl -s http://vault:8200/v1/sys/init | jq -r '.initialized')

if [ "$INITIALIZED" = "false" ]; then
  echo "Initializing Vault..."
  # Инициализация Vault
  INIT_RESPONSE=$(curl -s \
    --request POST \
    --data '{"secret_shares": 1, "secret_threshold": 1}' \
    http://vault:8200/v1/sys/init)

  # Извлекаем root token и unseal key
  ROOT_TOKEN=$(echo $INIT_RESPONSE | jq -r '.root_token')
  UNSEAL_KEY=$(echo $INIT_RESPONSE | jq -r '.keys[0]')

  echo "Root Token: $ROOT_TOKEN"
  echo "Unseal Key: $UNSEAL_KEY"

  # Unseal Vault
  curl -s \
    --request POST \
    --data "{\"key\": \"$UNSEAL_KEY\"}" \
    http://vault:8200/v1/sys/unseal

  # Создаем базовые секреты
  curl -s \
    --header "X-Vault-Token: $ROOT_TOKEN" \
    --request POST \
    --data '{"data": {"password": "mysecretpassword"}}' \
    http://vault:8200/v1/secret/data/db

  echo "Vault initialized and unsealed"
else
  echo "Vault already initialized"
fi 