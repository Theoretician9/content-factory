#!/bin/bash
# Account Manager Workers Startup Script

echo "🚀 Starting Account Manager Workers..."

# Настройка переменных окружения
export PYTHONPATH="/app:$PYTHONPATH"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"

# Ожидание готовности Redis и PostgreSQL
echo "⏳ Waiting for Redis and PostgreSQL..."
until redis-cli -h $REDIS_HOST -p $REDIS_PORT ping | grep -q PONG; do
  echo "Waiting for Redis..."
  sleep 2
done

echo "✅ Redis is ready"

until PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_SERVER -U $POSTGRES_USER -d $POSTGRES_DB -c '\q' 2>/dev/null; do
  echo "Waiting for PostgreSQL..."
  sleep 2
done

echo "✅ PostgreSQL is ready"

# Запуск Celery worker для Account Manager
echo "🔧 Starting Account Manager Celery Worker..."
exec python -m celery -A app.workers.account_manager_workers:celery_app worker \
  --loglevel=$LOG_LEVEL \
  --queues=account_manager_high,account_manager_normal,account_manager_low \
  --concurrency=2 \
  --hostname=account-manager-worker@%h \
  --pool=solo